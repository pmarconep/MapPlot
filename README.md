# MapPlot

A Python library for creating map images (2-D static maps) and interactive 3-D map plots with bars, scatter points, lines and elevation data.

## 3-D Map — Quick Start
```python
from staticmap import Map3D

m = Map3D(center=(-70.65, -33.45), zoom=12)

# 3-D bars
m.add_bars(
    [(-70.65, -33.45), (-70.64, -33.46)],
    [200, 350],
    color='steelblue',
)

# Scatter points with z-values
m.add_points(
    [(-70.63, -33.47)],
    [250],
    color='red',
    size=80,
)

# 3-D polyline
m.add_line(
    [(-70.65, -33.45), (-70.63, -33.47)],
    [200, 250],
    color='orange',
)

# Render — downloads OSM tiles automatically
fig, ax = m.render(
    show_map=True,          # drape satellite/street-map image as texture
    show_elevation=True,    # fetch SRTM elevation cloth (Open-Elevation API)
    title='Santiago 3-D',
    savefig='map3d.png',
)
```

![3-D Map Demo](/samples/map3d_demo.png?raw=true)

---

## 2-D Static Map — Quick Start
```python
from staticmap import StaticMap, Line

m = StaticMap(300, 400, 10)
m.add_line(Line(((13.4, 52.5), (2.3, 48.9)), 'blue', 3))
image = m.render()
image.save('map.png')
```
This will create a 300px × 400px map with a blue line drawn from Berlin to Paris.

![Map with Line from Berlin to Paris](/samples/berlin_paris.png?raw=true)


## Installation
MapPlot requires Python 3 and the following packages: [Pillow](https://python-pillow.github.io/), [requests](http://www.python-requests.org/), [NumPy](https://numpy.org/) and [Matplotlib](https://matplotlib.org/).

```bash
pip install staticmap
```

## 3-D Map API Reference

#### Create a `Map3D` instance:

```python
from staticmap import Map3D
m = Map3D(center, zoom, width=600, height=600, url_template=None, tile_size=256)
```

parameter       | description
--------------- | --------------------------------------------------
center          | ``(lon, lat)`` of the map centre
zoom            | OSM zoom level (0–19)
width           | backing tile-image width in pixels (default 600)
height          | backing tile-image height in pixels (default 600)
url_template    | tile URL, default OpenStreetMap
tile_size       | tile size in pixels (default 256)

#### Add 3-D bars:

```python
m.add_bars(coords, values, color='steelblue', bar_width=None, alpha=0.85)
```

parameter   | description
----------- | ---------------------------------------------------
coords      | list of ``(lon, lat)`` pairs
values      | bar heights (one per coordinate)
color       | Matplotlib colour spec
bar_width   | bar footprint in degrees (auto if *None*)
alpha       | opacity 0–1

#### Add scatter points:

```python
m.add_points(coords, values=None, color='red', size=50, alpha=0.9, marker='o')
```

parameter   | description
----------- | ---------------------------------------------------
coords      | list of ``(lon, lat)`` pairs
values      | z-axis values (defaults to 0 for every point)
color       | Matplotlib colour spec
size        | marker size in points²
marker      | Matplotlib marker style

#### Add a 3-D line:

```python
m.add_line(coords, values=None, color='blue', width=2, alpha=0.9)
```

parameter   | description
----------- | ---------------------------------------------------
coords      | list of ``(lon, lat)`` pairs (vertices)
values      | z-axis values (defaults to 0 for every vertex)
color       | Matplotlib colour spec
width       | line width in points

#### Render the plot:

```python
fig, ax = m.render(
    figsize=(12, 10), elev=30, azim=45,
    show_map=True, map_alpha=1.0, map_z=None,
    show_elevation=False, elevation_alpha=0.85,
    elevation_n_points=20, elevation_cmap='terrain',
    title=None, xlabel='Longitude', ylabel='Latitude', zlabel='Value',
    savefig=None, dpi=150,
)
```

parameter           | description
------------------- | ---------------------------------------------------
figsize             | Matplotlib figure size in inches
elev / azim         | camera elevation / azimuth angles
show_map            | drape tile image as a texture surface
show_elevation      | fetch SRTM elevation data (Open-Elevation API) and drape as a cloth surface
elevation_n_points  | grid resolution for the elevation surface
map_z               | z position of the flat map plane (auto if *None*)
savefig             | path to save the figure (skipped if *None*)

#### Fetch elevation data manually:

```python
LON, LAT, elevations = m.fetch_elevation(n_points=20)
```

Returns three 2-D NumPy arrays (longitude grid, latitude grid, elevation in metres) using the free [Open-Elevation](https://open-elevation.com) API (SRTM data, no API key required).

---

## 2-D Static Map API Reference
#### Create a new map instance:

```python
m = StaticMap(width, height, padding_x, padding_y, url_template, tile_size)
```

parameter           | description
------------------- | -------------
width               | width of the image in pixels
height              | height of the image in pixels
padding_x           | (optional) minimum distance in pixel between map features (lines, markers) and map border
padding_y           | (optional) minimum distance in pixel between map features (lines, markers) and map border
url_template        | (optional) the tile server URL for the map base layer, e.g. <code>http://a.tile.osm.org/{z}/{x}/{y}.png</code>
tile_size           | (optional) tile size in pixel, usually 256

#### Add a line:

```python
line = Line(coordinates, color, width))
m.add_line(line)
```

parameter     | description
------------- | -------------
coordinate    | a sequence of lon/lat pairs
color         | a color definition Pillow <a href="http://pillow.readthedocs.org/en/latest/reference/ImageColor.html#color-names">supports</a>
width         | the stroke width of the line in pixel
simplify      | whether to simplify coordinates, looks less shaky, default is true

#### Add a map circle marker:

```python
marker = CircleMarker(coordinate, color, width))
m.add_marker(marker)
```

parameter     | description
------------- | -------------
coordinate    | a lon/lat pair: e.g. `(120.1, 47.3)`
color         | a color definition Pillow <a href="http://pillow.readthedocs.org/en/latest/reference/ImageColor.html#color-names">supports</a>
width         | diameter of marker in pixel

#### Add a polygon:

```python
polygon = Polygon(coordinates, fill_color, outline_color, simplify)
m.add_polygon(polygon)
```

parameter     | description
------------- | -------------
coordinate    | a lon/lat pair: e.g. `[[9.628, 47.144], [9.531, 47.270], [9.468, 47.057], [9.623, 47.050], [9.628, 47.144]]`
fill_color    | a color definition Pillow <a href="http://pillow.readthedocs.org/en/latest/reference/ImageColor.html#color-names">supports</a>
outline_color | a color definition Pillow <a href="http://pillow.readthedocs.org/en/latest/reference/ImageColor.html#color-names">supports</a>
simplify      | whether to simplify coordinates, looks less shaky, default is true

## Samples
#### Show Position on Map
```python
from staticmap import StaticMap, CircleMarker

m = StaticMap(200, 200, url_template='http://a.tile.osm.org/{z}/{x}/{y}.png')

marker_outline = CircleMarker((10, 47), 'white', 18)
marker = CircleMarker((10, 47), '#0036FF', 12)

m.add_marker(marker_outline)
m.add_marker(marker)

image = m.render(zoom=5)
image.save('marker.png')
```

![Position IconMarker on a Map](/samples/marker.png?raw=true)

#### Show Ferry Connection
```python
from staticmap import StaticMap, Line

m = StaticMap(200, 200, 80)

coordinates = [[12.422, 45.427], [13.749, 44.885]]
line_outline = Line(coordinates, 'white', 6)
line = Line(coordinates, '#D2322D', 4)

m.add_line(line_outline)
m.add_line(line)

image = m.render()
image.save('ferry.png')
```

![Ferry Connection Shown on a Map](/samples/ferry.png?raw=true)

#### Show Icon Marker
```python
from staticmap import StaticMap, IconMarker

m = StaticMap(240, 240, 80)
icon_flag = IconMarker((6.63204, 45.85378), './samples/icon-flag.png', 12, 32)
icon_factory = IconMarker((6.6015, 45.8485), './samples/icon-factory.png', 18, 18)
m.add_marker(icon_flag)
m.add_marker(icon_factory)
image = m.render()
image.save('icons.png')
```

![Ferry Connection Shown on a Map](/samples/icons.png?raw=true)

### Alternatives
With [papermap](https://github.com/sgraaf/papermap) there is also a spin-off project dedicated to print maps.

### Licence
StaticMap is open source and licensed under Apache License, Version 2.0

The map samples on this page are made with [OSM](http://www.osm.org) data, © [OpenStreetMap](http://www.openstreetmap.org/copyright) contributors
