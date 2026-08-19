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
import dash_leaflet as dl
import urllib.parse

# Load CSV
df = pd.read_csv("DATA/EDIF_FINAL.csv")


# Example: UTM Zone 33N, WGS84
def get_svg_shape(shape_type, size, color):
    # Ensure minimum size
    s = max(size, 12) 
    
    if shape_type == "triangle":
        # Draws a triangle
        return f'<svg width="{s}" height="{s}"><polygon points="{s/2},0 {s},{s} 0,{s}" fill="{color}" opacity="0.8" stroke="black" stroke-width="1"/></svg>'
    elif shape_type == "square":
        # Draws a square
        return f'<svg width="{s}" height="{s}"><rect x="0" y="0" width="{s}" height="{s}" fill="{color}" opacity="0.8" stroke="black" stroke-width="1"/></svg>'
    else:
        # Defaults to a circle
        return f'<svg width="{s}" height="{s}"><circle cx="{s/2}" cy="{s/2}" r="{s/2}" fill="{color}" opacity="0.8" stroke="black" stroke-width="1"/></svg>'



features = []

for _, row in df.iterrows():
    lat = row['LATITUD']
    lon = row['LONGITUD']


    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lat, lon],
        },
        "properties":{
            "obs":row["OBS"],
            "plantas":row['PLANTAS'],
            'huella':row['HUELLA(M2)'],
            'config':row['CONFIG'],
            'edif':row['EDIF']
        }
    }
    features.append(feature)

geojson = {
    "type": "FeatureCollection",
    "features": features
}

with open("edif.geojson", "w") as f:
    json.dump(geojson, f, indent=2)


with open("edif.geojson", "r", encoding="utf-8") as file:
    edif_geojson = json.load(file)

rows = []

for feature in edif_geojson["features"]:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})

    if geometry.get("type") != "Point":
        continue

    latitude, longitude = geometry["coordinates"][:2]
#ROWS.APPEND
    rows.append(
        {
        "EDIF": properties.get("edif"),
        "lat": latitude,
        "lon": longitude,
        "PLANTAS": properties.get("plantas"),
        "HUELLA": properties.get("huella"),
        "CONFIG": properties.get('config'),
        "OBS":properties.get("obs")
        }
)


df1 = pd.DataFrame(rows)
print(df1)

df1=df1.dropna(subset=['lat','lon'])
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
                html.Strong(row["EDIF"]),
            ],
            id={
                "type": "point-item",
                "index": str(row["EDIF"]),
            },
            n_clicks=0,
            action=True,
            style={"cursor": "pointer"},
        )
        for _, row in dataframe.iterrows()
    ]


def asignar_simbolo(valor):
    if valor == 1:
        return "Base"
    elif valor == 2:
        return "Azotea + Base"
    elif valor ==3:
        return "square"
    else:
        return "diamond"


df1["symbol"] = df1["CONFIG"].apply(asignar_simbolo)
print(df1)

def create_map(dataframe, selected_id=None):
    df_map = dataframe.copy()
    df_map["EDIF"] = df_map["EDIF"].astype(str).str.strip()

    # Center and Zoom logic
    center_lat = df_map["lat"].mean()
    center_lon = df_map["lon"].mean()
    zoom = 13

    if selected_id is not None:
        selected_id = str(selected_id).strip()
        selected_rows = df_map[df_map["EDIF"] == selected_id]
        if not selected_rows.empty:
            center_lat = float(selected_rows.iloc[0]["lat"])
            center_lon = float(selected_rows.iloc[0]["lon"])
            zoom = 16

    size_scaler = 20
    markers = []

    # SINGLE LOOP TO CREATE ALL MARKERS
    for _, row in df_map.iterrows():
        lat = row.get("lat")
        lon = row.get("lon")
        
        # Skip rows with missing coordinates
        if pd.isna(lat) or pd.isna(lon):
            continue

        lat = float(lat)
        lon = float(lon)

        # 1. Map CONFIG to numbers safely
        raw_config = row.get("CONFIG")
        if pd.isna(raw_config):
            config_val = -1 
        else:
            config_val = int(float(raw_config)) 

        color_map = {1: "#1f77b4", 2: "#ff7f0e", 3: "#2ca02c"}
        shape_map = {1: "circle", 2: "triangle", 3: "square"}

        color = color_map.get(config_val, "gray")
        shape = shape_map.get(config_val, "circle")

        # 2. Check if selected and determine size
        edif_id = str(row.get("EDIF", ""))
        if edif_id == selected_id:
            color = "#d62728" # Red if selected
            
        huella = row.get("HUELLA")
        if pd.isna(huella):
            huella = 200 
            
        calculated_size = huella / size_scaler
        final_size = calculated_size * 1.5 if edif_id == selected_id else calculated_size
        final_size = max(15, final_size) # Minimum size of 15px

        # 3. Create Tooltip Text
        tooltip_text = (
            f"Edificio: {edif_id} | "
            f"Config: {config_val} | "
            f"Plantas: {row.get('PLANTAS', 'N/A')} | "
            f"Huella: {huella} m²"
        )

        # 4. GENERATE DYNAMIC SVG SHAPE (Inside the loop!)
        r = (final_size / 2) - 1
        c = final_size / 2
        w = final_size - 2

        if shape == "triangle":
            svg_element = f'<polygon points="{c},1 {w+1},{w+1} 1,{w+1}" fill="{color}" stroke="black" stroke-width="1.5"/>'
        elif shape == "square":
            svg_element = f'<rect x="1" y="1" width="{w}" height="{w}" fill="{color}" stroke="black" stroke-width="1.5"/>'
        else: 
            svg_element = f'<circle cx="{c}" cy="{c}" r="{r}" fill="{color}" stroke="black" stroke-width="1.5"/>'

        # Add viewBox and xmlns
        svg_string = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {final_size} {final_size}" width="{final_size}" height="{final_size}">{svg_element}</svg>'
        
        # URL-encode and add charset=UTF-8
        encoded_svg = urllib.parse.quote(svg_string)
        icon_url = f"data:image/svg+xml;charset=UTF-8,{encoded_svg}"

        # 5. Create the Marker and APPEND IT
        custom_icon = dl.Marker(
            position=[lat, lon],
            children=[dl.Tooltip(tooltip_text)],
            icon=dict(
                iconUrl=icon_url,
                iconSize=[final_size, final_size], 
                iconAnchor=[c, c],
                className="" 
            )
        )
        markers.append(custom_icon)

    print(f"Created {len(markers)} markers")

    # Return the Dash Leaflet Map component
    return dl.Map(
        center=[center_lat, center_lon],
        zoom=zoom,
        children=[
            dl.TileLayer(), # Default is OpenStreetMap
            dl.LayerGroup(markers)
        ],
        style={'width': '100%', 'height': '600px'}
    )



config_options = [{"label": c, "value": c} for c in sorted(df["CONFIG"].dropna().unique())]


app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY
    ]
)

server = app.server

point_list = dbc.ListGroup([
    dbc.ListGroupItem([
        html.Strong(row["EDIF"]),
        html.Br(),
        html.Small(
            f"Lat: {row['LATITUD']:.4f}, "
            f"Lon: {row['LONGITUD']:.4f}, "
        )
    ])
    for _, row in df.iterrows()
])

app.layout = dbc.Container([
    html.H1("Edificios Instrumentados PINS",
            style={
                        "textAlign": "center",
                        }),
   
         dbc.Row(
            [
                # Lista y buscador
                dbc.Col(
                    [
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
                    width=2,
                    style={
                        "minWidth": 0
                    },
                ),

                # Mapa
                dbc.Col(
                    [
                        html.Div([
                           create_map(df1)
                        ],
                        id="map-container")
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
            "Elaborado por Grupo PINS-FIC",
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
    Output("map-container", "children"),
    Output("selected-point", "children"),
     Input(
        {"type": "point-item", "index": ALL},
        "n_clicks",
    ),
    prevent_initial_call=True,
)
def select_point(n_clicks_list): # Changed parameter name to reflect what Dash actually sends
    triggered_id = ctx.triggered_id

    if not triggered_id:
        return (
            create_map(df1), # Ensure this calls your Dash Leaflet map function
            "Seleccione un Edificio de la lista.",
        )

    # Extract the actual ID from the trigger context
    actual_selected_id = str(triggered_id["index"])

    selected_rows = df1[
        df1["EDIF"].astype(str) == actual_selected_id
    ]

    if selected_rows.empty:
        return (
            create_map(df1), # Ensure this calls your Dash Leaflet map function
            "No se encontró el edificio seleccionado.",
        )

    selected_row = selected_rows.iloc[0]

    return (
        create_map(df1, actual_selected_id), # Ensure this calls your Dash Leaflet map function
        dbc.Alert(
            [
                html.Strong(
                    f'Seleccionado: {selected_row["EDIF"]}'
                ),
            ],
            color="primary",
        ),
    )



if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8050)),
        debug=False
    )
