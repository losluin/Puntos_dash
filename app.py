# app.py
from dash import Dash, dcc, html, Input, Output, ctx, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import geopandas as gpd
import json
import numpy as np
import os
from pyproj import CRS, Transformer

# Load CSV
df = pd.read_csv("puntos.csv")

# Example: UTM Zone 33N, WGS84
utm_crs = CRS.from_epsg(32617)   # change to your UTM EPSG
wgs84 = CRS.from_epsg(4326)

transformer = Transformer.from_crs(utm_crs, wgs84, always_xy=True)

features = []

for _, row in df.iterrows():
    lon, lat = transformer.transform(row["ESTE"], row["NORTE"])

    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "properties":{
            "DESCRIPCIÓN":row["DESCRIPCIÓN"],
            "NORTE":row['NORTE'],
            'ESTE':row['ESTE'],
            'ELEV':row['COTA'],
            'id':row['N°']
        }
    }
    features.append(feature)

geojson = {
    "type": "FeatureCollection",
    "features": features
}

with open("points.geojson", "w") as f:
    json.dump(geojson, f, indent=2)


with open("points.geojson", "r", encoding="utf-8") as file:
    points_geojson = json.load(file)

rows = []

for feature in points_geojson["features"]:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})

    if geometry.get("type") != "Point":
        continue

    longitude, latitude = geometry["coordinates"][:2]

    rows.append(
    {
        "id": properties.get("N°", properties.get("id", "")),
        "name": properties.get(
            "name",
            properties.get("DESCRIPCIÓN", "Sin nombre"),
        ),
        "lat": latitude,
        "lon": longitude,
        "este": properties.get("ESTE"),
        "norte": properties.get("NORTE"),
        "elev":properties.get("ELEV")
    }
)


df1 = pd.DataFrame(rows)
print(df1)

def crear_lista(dataframe):
    if dataframe.empty:
        return dbc.ListGroupItem(
            "No se encontraron puntos.",
            color="light",
        )

    return [
        dbc.ListGroupItem(
            [
                html.Strong(row["name"]),
                html.Br(),
                html.Small(
                    f'NORTE: {row["norte"]:.4f},     '
                    f'ESTE: {row["este"]:.4f},    '
                    f'ELEV.: {row["elev"]:.4f}    '
                ),
            ],
            id={
                "type": "point-item",
                "index": str(row["id"]),
            },
            n_clicks=0,
            action=True,
            style={"cursor": "pointer"},
        )
        for _, row in dataframe.iterrows()
    ]

def create_map(
    dataframe,
    selected_id=None,
    center_lat=9.023826,
    center_lon=-79.531796,
    zoom=15,
    show_grid=True,
    grid_labels=True
):
    dataframe = dataframe.copy()

    dataframe["id"] = dataframe["id"].astype(str).str.strip()

    if selected_id is not None:
        selected_id = str(selected_id).strip()

    colors = [
        "blue" if point_id == selected_id else "red"
        for point_id in dataframe["id"]
    ]

    sizes = [
        10 if point_id == selected_id else 5
        for point_id in dataframe["id"]
    ]

    markers = [
        "square" if point_id == selected_id else "square-stroked"
        for point_id in dataframe['id']
    ]

    customdata = np.column_stack(
        [
            dataframe["id"],
            dataframe["este"].fillna(""),
            dataframe["norte"].fillna(""),
            dataframe["elev"].fillna(""),
        ]
    )

    fig = go.Figure(
        go.Scattermap(
            lat=dataframe["lat"],
            lon=dataframe["lon"],
            mode="markers",
            marker={
                "size": sizes,
                "color": colors,
            },
            text=dataframe["name"],
            customdata=customdata,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "ESTE: %{customdata[1]}<br>"
                "NORTE: %{customdata[2]}<br>"
                "ELEV.: %{customdata[3]}"
                "<extra></extra>"
            ),
        )
    )

    # Centrar el mapa en el punto seleccionado
    if selected_id is not None:
        selected_rows = dataframe[
            dataframe["id"] == selected_id
        ]

        if not selected_rows.empty:
            selected_row = selected_rows.iloc[0]
            center_lat = float(selected_row["lat"])
            center_lon = float(selected_row["lon"])
            zoom = 17

    fig.update_layout(
        map={
            "style": "carto-voyager",
            "center": {
                "lat": center_lat,
                "lon": center_lon,
            },
            "zoom": zoom,
        },
        height=600,
        margin={
            "r": 0,
            "t": 0,
            "l": 0,
            "b": 0,
        },
    )
    return fig

app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY
    ]
)

server = app.server

point_list = dbc.ListGroup([
    dbc.ListGroupItem([
        html.Strong(row["DESCRIPCIÓN"]),
        html.Br(),
        html.Small(
            f"Lat: {row['NORTE']:.4f}, "
            f"Lon: {row['ESTE']:.4f}, "
        )
    ])
    for _, row in df.iterrows()
])

app.layout = dbc.Container([
    html.H3("Puntos VLS-UTP"),
    html.H4("ELIPSOIDE EGM08"),
    html.H4('MARCO DE REFENCIA ITRF08'),
         dbc.Row(
            [
                # Lista y buscador
                dbc.Col(
                    [
                        dbc.Input(
                            id="search-bar",
                            type="search",
                            placeholder="Buscar punto...",
                            debounce=True,
                            className="mb-3",
                        ),

                        dbc.ListGroup(
                            id="point-list",
                            children=crear_lista(df1),
                            style={
                                "height": "600px",
                                "overflowY": "auto",
                            },
                        ),

                        html.Hr(),

                        html.Div(id="selected-point"),
                    ],
                    width=3,
                    style={
                        "minWidth": 0
                    },
                ),

                # Mapa
                dbc.Col(
                    [
                        dcc.Graph(
                            id="map",
                            figure=create_map(df1),
                            style={
                                "height": "600px",
                                "width": "100%",
                            },
                            config={
                                "responsive": True,
                            },
                        )
                    ],
                    width=8,
                    style={
                        "minWidth": 0
                    },
                ),
            ],
            className="g-3",
            style={
                "margin": 0,
            },
        ),
        html.Footer(
            "Elaborado por Carlos Calderon, David Gaitán e Isaac López | Sitio por Daniel Madrid",
              style={
            "textAlign": "center",
            "padding": "15px",
            "marginTop": "20px",
            "borderTop": "1px solid #ccc",
            "color": "#666",
            "fontSize": "14px",
            },
            )
    ],
    fluid=True,
    className="p-4",
)



@app.callback(
    Output("map", "figure"),
    Output("selected-point", "children"),
    Input(
        {"type": "point-item", "index": ALL},
        "n_clicks",
    ),
    prevent_initial_call=True,
)
def select_point(selected_id):
    triggered_id = ctx.triggered_id

    if not triggered_id:
        return (
            create_map(df1),
            "Seleccione una ubicación de la lista.",
        )

    selected_id = str(triggered_id["index"])

    selected_rows = df1[
        df1["id"].astype(str) == selected_id
    ]

    if selected_rows.empty:
        return (
            create_map(df1),
            "No se encontró la ubicación seleccionada.",
        )

    selected_row = selected_rows.iloc[0]

    return (
        create_map(df1, selected_id),
        dbc.Alert(
            [
                html.Strong(
                    f'Seleccionado: {selected_row["name"]}'
                ),
                html.Br(),
                f'ID: {selected_row["id"]}',
            ],
            color="primary",
        ),
    )

@app.callback(
    Output("point-list", "children"),
    Input("search-bar", "value"),
)
def update_point_list(search_text):
    data = df1.copy()

    search_text = (
        str(search_text).strip().lower()
        if search_text
        else ""
    )

    if search_text:
        data = data[
            data["name"]
            .str.lower()
            .str.contains(search_text, na=False)
        ]

    return crear_lista(data)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8050)),
        debug=False
    )
