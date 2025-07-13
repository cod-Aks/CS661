import pandas as pd
import geopandas as gpd
import numpy as np
from dash import Dash, dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# === Load data ===
df_hist = pd.read_csv(r"Loksabha_1962-2019 .csv")
geo = gpd.read_file(
    r"india_pc_2019_simplified.geojson"
)

# === Clean and Preprocess ===
df_hist["party"] = df_hist["party"].astype(str).str.strip().str.title()

# ✅ Add this mapping for party names
party_map = {
    "Bharatiya Janata Party": "BJP",
    "Indian National Congress": "INC",
    "Bahujan Samaj Party": "BSP",
    "Aam Aadmi Party": "AAP",
    "Communist Party Of India (Marxist)": "CPM",
    "All India Trinamool Congress": "TMC",
    "Janata Dal (United)": "JDU",
    "Samajwadi Party": "SP",
}
df_hist["party"] = df_hist["party"].replace(party_map)

df_hist["year"] = pd.to_numeric(df_hist["year"], errors="coerce")

# Clean & convert turnout, votes, electors
df_hist["Turnout"] = pd.to_numeric(
    df_hist["Turnout"].astype(str).str.replace("%", "", regex=False), errors="coerce"
)
df_hist["margin%"] = pd.to_numeric(
    df_hist["margin%"].astype(str).str.replace("%", "", regex=False), errors="coerce"
)
df_hist["votes"] = pd.to_numeric(
    df_hist["votes"].astype(str).str.replace(",", "", regex=False), errors="coerce"
)
df_hist["electors"] = pd.to_numeric(
    df_hist["electors"].astype(str).str.replace(",", "", regex=False), errors="coerce"
)

df_hist = df_hist.dropna(subset=["Turnout", "votes", "electors"])
df_hist["Turnout"] = (df_hist["votes"] / df_hist["electors"]) * 100

# === Regional Dominance ===
df_dom = df_hist.dropna(subset=["state", "party", "year"])
dominant = (
    df_dom.groupby(["state", "year", "party"])
    .size()
    .reset_index(name="seats")
    .sort_values(["state", "year", "seats"], ascending=[True, True, False])
    .drop_duplicates(["state", "year"])
)
state_party_dominance = (
    dominant.groupby(["state", "party"]).size().reset_index(name="times_dominated")
)

# === Constituency Map (all years) ===
# Clean constituency names for better matching
df_hist["Pc_name"] = df_hist["Pc_name"].str.strip().str.title()
geo["pc_name"] = geo["pc_name"].str.strip().str.title()

# Get all years available in the dataset
available_years = sorted(df_hist["year"].dropna().unique())

# === Turnout Heatmap Data ===
turnout_top = (
    df_hist.sort_values(["state", "year", "Turnout"], ascending=[True, True, False])
    .groupby(["state", "year"])
    .head(10)
)

# === App Layout ===
app = Dash(__name__)
states = sorted(df_hist["state"].dropna().unique())

app.layout = html.Div(
    style={"fontFamily": "Arial"},
    children=[
        html.H1(
            "Indian General Elections Dashboard",
            style={"textAlign": "center", "color": "#2c3e50"},
        ),
        dcc.Tabs(
            [
                dcc.Tab(
                    label="🗺️ Constituency Map",
                    children=[
                        html.Div(
                            [
                                html.Label(
                                    "Select Year:",
                                    style={"padding": "10px", "fontWeight": "bold"},
                                ),
                                dcc.Dropdown(
                                    id="year-dropdown",
                                    options=[
                                        {"label": str(int(year)), "value": year}
                                        for year in available_years
                                    ],
                                    value=available_years[-1],  # Default to latest year
                                    style={"width": "200px", "margin": "10px"},
                                ),
                            ],
                            style={
                                "display": "flex",
                                "alignItems": "center",
                                "justifyContent": "center",
                            },
                        ),
                        dcc.Graph(id="map-graph"),
                    ],
                ),
                dcc.Tab(
                    label="🗺️ Margin% Map",
                    children=[
                        html.Div(
                            [
                                html.Label(
                                    "Select Year:",
                                    style={"padding": "10px", "fontWeight": "bold"},
                                ),
                                dcc.Dropdown(
                                    id="margin-year-dropdown",
                                    options=[
                                        {"label": str(int(year)), "value": year}
                                        for year in available_years
                                    ],
                                    value=available_years[-1],
                                    style={"width": "200px", "margin": "10px"},
                                ),
                            ],
                            style={
                                "display": "flex",
                                "alignItems": "center",
                                "justifyContent": "center",
                            },
                        ),
                        dcc.Graph(id="margin-map-graph"),
                    ],
                ),
                dcc.Tab(
                    label="🌞 Repeat Winners Sunburst",
                    children=[dcc.Graph(id="sunburst-chart")],
                ),
                dcc.Tab(
                    label="📈 Historical Party Performance",
                    children=[dcc.Graph(id="hist-graph")],
                ),
                dcc.Tab(
                    label="📊 Voter Turnout Analysis",
                    children=[
                        html.Label("Select State:", style={"padding": "10px"}),
                        dcc.Dropdown(
                            id="state-dropdown",
                            options=[{"label": s, "value": s} for s in states],
                            value=states[0],
                        ),
                        dcc.Graph(id="turnout-heatmap"),
                    ],
                ),
                dcc.Tab(
                    label="🏆 Regional Party Dominance",
                    children=[dcc.Graph(id="dominance-graph")],
                ),
            ]
        ),
    ],
)

# === Callbacks ===


@app.callback(Output("map-graph", "figure"), Input("year-dropdown", "value"))
def plot_map(selected_year):
    # Filter data for selected year
    df_year = df_hist[df_hist["year"] == selected_year][
        ["Pc_name", "party", "candidate_name"]
    ].drop_duplicates()

    # Merge with geography data
    merged_map = geo.merge(df_year, left_on="pc_name", right_on="Pc_name", how="left")
    merged_map["party"] = merged_map["party"].fillna("OTHER")

    # Create color mapping for parties
    color_map = {
        "BJP": "#FF9933",
        "INC": "#008000",
        "BSP": "#0000FF",
        "AAP": "#00CED1",
        "CPM": "#FF0000",
        "TMC": "#00FF00",
        "JDU": "#FFFF00",
        "SP": "#800080",
        "OTHER": "#808080",
    }

    fig = px.choropleth(
        merged_map,
        geojson=merged_map.geometry,
        locations=merged_map.index,
        color="party",
        hover_name="pc_name",
        hover_data="candidate_name",
        title=f"Winning Party by Constituency ({int(selected_year)})",
        color_discrete_map=color_map,
        height=1000,
        width=1650,
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 0, "t": 50, "l": 0, "b": 0}, font=dict(size=12), autosize=False
    )

    return fig


bins = [0, 1, 5, 10, 15, 20, 30, 40, 50, 100]
labels = ["0-1", "1-5", "5-10", "10-15", "15-20", "20-30", "30-40", "40-50", "50-100"]

df_hist["margin_color"] = pd.cut(
    df_hist["margin%"], bins=bins, labels=labels, include_lowest=True, right=True
)

df_hist["margin_color"] = df_hist["margin_color"].cat.add_categories(["gray"])
df_hist["margin_color"] = df_hist["margin_color"].fillna("gray")


@app.callback(
    Output("margin-map-graph", "figure"), Input("margin-year-dropdown", "value")
)
def plot_margin_map(selected_year):
    df_year = df_hist[df_hist["year"] == selected_year][
        ["Pc_name", "margin%", "margin_color", "party"]
    ].drop_duplicates()
    merged_map = geo.merge(df_year, left_on="pc_name", right_on="Pc_name", how="left")
    merged_map["margin_color"] = merged_map["margin_color"].fillna(
        "gray"
    )  # For missing data

    color_discrete_map = {
        "0-1": "maroon",
        "1-5": "red",
        "5-10": "orange",
        "10-15": "yellow",
        "15-20": "lime",
        "20-30": "lightgreen",
        "30-40": "darkgreen",
        "40-50": "skyblue",
        "50-100": "darkblue",
        "gray": "gray",
    }

    fig = px.choropleth(
        merged_map,
        geojson=merged_map.geometry,
        locations=merged_map.index,
        color="margin_color",
        hover_name="pc_name",
        hover_data="party",
        title=f"Victory Margin% by Constituency ({int(selected_year)})",
        color_discrete_map=color_discrete_map,
        height=1000,
        width=1650,
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 10, "t": 100, "l": 10, "b": 10}, font=dict(size=12), autosize=False
    )
    return fig


# Count wins by candidate and party
candidate_wins = (
    df_hist.groupby(["candidate_name", "party"]).size().reset_index(name="wins")
)

# Filter candidates with more than 5 wins
top_candidates = candidate_wins[candidate_wins["wins"] > 5]

# Prepare data for sunburst: party as inner, candidate as outer
sunburst_data = top_candidates[["party", "candidate_name", "wins"]]

import plotly.express as px


@app.callback(Output("sunburst-chart", "figure"), Input("sunburst-chart", "id"))
def plot_sunburst(_):
    # Use the prepared sunburst_data DataFrame
    fig = px.sunburst(
        sunburst_data,
        path=["party", "candidate_name"],
        values="wins",
        color="party",
        title="Candidates Who Won More Than 5 Times (by Party)[The Pro Players]",
        height=1300,
        width=1300,
    )
    fig.update_layout(margin=dict(t=50, l=450, r=0, b=0), font=dict(size=14))
    return fig


@app.callback(Output("hist-graph", "figure"), Input("hist-graph", "id"))
def plot_history(_):
    major_parties = ["BJP", "INC", "BSP", "AAP", "CPM", "TMC", "JDU", "SP"]
    grouped = (
        df_hist[df_hist["party"].isin(major_parties)]
        .groupby(["year", "party"])
        .agg(
            seats=("Pc_name", "count"),
            total_votes=("votes", "sum"),
            avg_turnout=("Turnout", "mean"),
        )
        .reset_index()
    )

    if grouped.empty:
        return go.Figure().update_layout(title="No historical data available.")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for party in grouped["party"].unique():
        df_party = grouped[grouped["party"] == party]
        fig.add_trace(
            go.Scatter(
                x=df_party["year"],
                y=df_party["seats"],
                mode="lines+markers",
                name=party,
            ),
            secondary_y=False,
        )

    votes_total = grouped.groupby("year")["total_votes"].sum().reset_index()
    turnout_mean = grouped.groupby("year")["avg_turnout"].mean().reset_index()

    fig.add_trace(
        go.Scatter(
            x=votes_total["year"],
            y=votes_total["total_votes"],
            mode="lines",
            name="Total Votes",
            line=dict(color="black", dash="dot"),
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=turnout_mean["year"],
            y=turnout_mean["avg_turnout"],
            mode="lines",
            name="Avg Turnout",
            line=dict(color="gray", dash="dash"),
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title="Historical Performance (1962–2024)",
        xaxis_title="Year",
        yaxis_title="Seats Won",
        yaxis2_title="Votes / Turnout (%)",
        hovermode="x unified",
        height=900,  # Set height here
        width=1500,  # Set width here
    )
    return fig


@app.callback(Output("turnout-heatmap", "figure"), Input("state-dropdown", "value"))
def plot_heatmap(state):
    df = turnout_top[turnout_top["state"] == state]
    if df.empty:
        return go.Figure().update_layout(
            title="No data available for selected state.",
            xaxis_title="Year",
            yaxis_title="Constituency",
        )
    df["Pc_name"] = df["Pc_name"].str.strip().str.title()
    pivot = df.pivot_table(
        index="Pc_name", columns="year", values="Turnout", aggfunc="mean", fill_value=0
    )
    top_10 = (
        df.groupby("Pc_name")["Turnout"]
        .mean()
        .sort_values(ascending=False)
        .head(10)
        .index
    )
    data = pivot.loc[top_10]
    fig = px.imshow(
        data,
        labels=dict(x="Year", y="Constituency", color="Turnout (%)"),
        title=f"Top 10 Turnout Constituencies in {state}",
        color_continuous_scale="Viridis",
        height=900,  # Set height here
        width=1500,  # Set width here
    )
    fig.update_xaxes(side="top")
    return fig


@app.callback(Output("dominance-graph", "figure"), Input("dominance-graph", "id"))
def plot_dom_graph(_):
    top = state_party_dominance.sort_values(by="times_dominated", ascending=False).head(
        25
    )
    fig = px.bar(
        top,
        x="state",
        y="times_dominated",
        color="party",
        title="Most Dominant Parties by State (1962–2024)",
        height=900,  # Set height here
        width=1650,  # Set width here
    )
    return fig


# === Run App ===
if __name__ == "__main__":
    app.run(debug=True)
