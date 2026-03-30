import itertools
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from math import log, tan, pi, cos, ceil, floor, atan, sinh

import numpy as np
import requests
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 – ensures 3D projection is registered (required for Matplotlib < 3.2)
from PIL import Image


def _lon_to_x(lon, zoom):
    if not (-180 <= lon <= 180):
        lon = (lon + 180) % 360 - 180
    return ((lon + 180.0) / 360) * pow(2, zoom)


def _lat_to_y(lat, zoom):
    if not (-90 <= lat <= 90):
        lat = (lat + 90) % 180 - 90
    return (1 - log(tan(lat * pi / 180) + 1 / cos(lat * pi / 180)) / pi) / 2 * pow(2, zoom)


def _y_to_lat(y, zoom):
    return atan(sinh(pi * (1 - 2 * y / pow(2, zoom)))) / pi * 180


def _x_to_lon(x, zoom):
    return x / pow(2, zoom) * 360.0 - 180.0


class Map3D:
    """
    3-D map plot that overlays data (bars, scatter points, lines) and an optional
    elevation cloth on top of a stitched satellite / street-map tile image.

    Quick example::

        from staticmap.plots import Map3D

        m = Map3D(center=(-70.65, -33.45), zoom=12)
        m.add_bars([(-70.65, -33.45), (-70.64, -33.46)], [200, 350], color='steelblue')
        fig, ax = m.render(show_elevation=True, title='Santiago, Chile')
        fig.savefig('map3d.png', dpi=150)
    """

    DEFAULT_TILE_URL = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
    ELEVATION_API_URL = "https://api.open-elevation.com/api/v1/lookup"

    def __init__(
        self,
        center,
        zoom,
        width=600,
        height=600,
        url_template=None,
        tile_size=256,
        tile_request_timeout=None,
        headers=None,
        delay_between_retries=0,
    ):
        """
        :param center: ``(lon, lat)`` centre of the map
        :type center: tuple
        :param zoom: OSM zoom level (0–19)
        :type zoom: int
        :param width: width of the backing map image in pixels
        :type width: int
        :param height: height of the backing map image in pixels
        :type height: int
        :param url_template: tile URL template, e.g.
            ``"https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"``
        :type url_template: str
        :param tile_size: tile size in pixels (default 256)
        :type tile_size: int
        :param tile_request_timeout: per-request timeout in seconds
        :type tile_request_timeout: float or None
        :param headers: extra HTTP headers for tile requests
        :type headers: dict or None
        :param delay_between_retries: seconds to wait between retry attempts
        :type delay_between_retries: float
        """
        self.center = center
        self.zoom = zoom
        self.width = width
        self.height = height
        self.url_template = url_template or self.DEFAULT_TILE_URL
        self.tile_size = tile_size
        self.request_timeout = tile_request_timeout
        self.headers = headers or {"User-Agent": "MapPlot"}
        self.delay_between_retries = delay_between_retries

        # Centre in tile coordinates
        self.x_center = _lon_to_x(center[0], zoom)
        self.y_center = _lat_to_y(center[1], zoom)

        # Geographic extent of the rendered image
        x_min_tile = self.x_center - 0.5 * width / tile_size
        x_max_tile = self.x_center + 0.5 * width / tile_size
        y_min_tile = self.y_center - 0.5 * height / tile_size
        y_max_tile = self.y_center + 0.5 * height / tile_size

        self.lon_min = _x_to_lon(x_min_tile, zoom)
        self.lon_max = _x_to_lon(x_max_tile, zoom)
        # Note: Mercator y increases downward, so higher tile y → smaller lat
        self.lat_min = _y_to_lat(y_max_tile, zoom)
        self.lat_max = _y_to_lat(y_min_tile, zoom)

        # Overlay feature lists
        self._bars = []
        self._points = []
        self._lines = []

    # ------------------------------------------------------------------
    # Public feature-addition methods
    # ------------------------------------------------------------------

    def add_bars(self, coords, values, color="steelblue", bar_width=None, alpha=0.85):
        """
        Add 3-D vertical bars anchored at geographic coordinates.

        :param coords: sequence of ``(lon, lat)`` pairs
        :type coords: list[tuple]
        :param values: bar heights (z-axis values), one per coordinate
        :type values: list[float]
        :param color: bar colour (any Matplotlib colour spec)
        :type color: str
        :param bar_width: bar footprint in degrees; defaults to ~2 % of the
            narrower map dimension
        :type bar_width: float or None
        :param alpha: opacity (0–1)
        :type alpha: float
        """
        if bar_width is None:
            bar_width = min(self.lon_max - self.lon_min, self.lat_max - self.lat_min) * 0.02
        self._bars.append(
            {
                "coords": list(coords),
                "values": list(values),
                "color": color,
                "bar_width": bar_width,
                "alpha": alpha,
            }
        )

    def add_points(self, coords, values=None, color="red", size=50, alpha=0.9, marker="o"):
        """
        Add a 3-D scatter plot over the map.

        :param coords: sequence of ``(lon, lat)`` pairs
        :type coords: list[tuple]
        :param values: z-axis values; defaults to 0 for each point
        :type values: list[float] or None
        :param color: marker colour
        :type color: str
        :param size: marker size in points²
        :type size: float
        :param alpha: opacity (0–1)
        :type alpha: float
        :param marker: Matplotlib marker style
        :type marker: str
        """
        if values is None:
            values = [0.0] * len(list(coords))
        self._points.append(
            {
                "coords": list(coords),
                "values": list(values),
                "color": color,
                "size": size,
                "alpha": alpha,
                "marker": marker,
            }
        )

    def add_line(self, coords, values=None, color="blue", width=2, alpha=0.9):
        """
        Add a 3-D polyline over the map.

        :param coords: sequence of ``(lon, lat)`` pairs
        :type coords: list[tuple]
        :param values: z-axis values; defaults to 0 for each vertex
        :type values: list[float] or None
        :param color: line colour
        :type color: str
        :param width: line width in points
        :type width: float
        :param alpha: opacity (0–1)
        :type alpha: float
        """
        if values is None:
            values = [0.0] * len(list(coords))
        self._lines.append(
            {
                "coords": list(coords),
                "values": list(values),
                "color": color,
                "width": width,
                "alpha": alpha,
            }
        )

    # ------------------------------------------------------------------
    # Elevation data
    # ------------------------------------------------------------------

    def fetch_elevation(self, n_points=20):
        """
        Retrieve elevation data for the map extent from the free
        `Open-Elevation <https://open-elevation.com>`_ API (SRTM data).

        :param n_points: number of grid samples per axis
        :type n_points: int
        :return: ``(LON, LAT, elevations)`` – three 2-D arrays shaped
            ``(n_points, n_points)``
        :rtype: tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]
        """
        lons = np.linspace(self.lon_min, self.lon_max, n_points)
        lats = np.linspace(self.lat_min, self.lat_max, n_points)
        LON, LAT = np.meshgrid(lons, lats)

        locations = [
            {"latitude": float(lat), "longitude": float(lon)}
            for lat, lon in zip(LAT.ravel(), LON.ravel())
        ]

        try:
            response = requests.post(
                self.ELEVATION_API_URL,
                json={"locations": locations},
                timeout=30,
            )
            response.raise_for_status()
            results = response.json()["results"]
            elevations = np.array([r["elevation"] for r in results]).reshape(
                n_points, n_points
            )
        except Exception as exc:
            print(f"Warning: could not fetch elevation data ({exc}); using flat surface.")
            elevations = np.zeros((n_points, n_points))

        return LON, LAT, elevations

    # ------------------------------------------------------------------
    # Internal tile-fetching helpers
    # ------------------------------------------------------------------

    def _x_to_px(self, x):
        return int(round((x - self.x_center) * self.tile_size + self.width / 2))

    def _y_to_px(self, y):
        return int(round((y - self.y_center) * self.tile_size + self.height / 2))

    def _get_tile(self, url):
        res = requests.get(url, timeout=self.request_timeout, headers=self.headers)
        return res.status_code, res.content

    def _fetch_map_image(self):
        """Download and stitch OSM tiles into a single PIL Image."""
        image = Image.new("RGB", (self.width, self.height), "#ffffff")

        x_min = int(floor(self.x_center - 0.5 * self.width / self.tile_size))
        y_min = int(floor(self.y_center - 0.5 * self.height / self.tile_size))
        x_max = int(ceil(self.x_center + 0.5 * self.width / self.tile_size))
        y_max = int(ceil(self.y_center + 0.5 * self.height / self.tile_size))

        tiles = []
        for x in range(x_min, x_max):
            for y in range(y_min, y_max):
                max_tile = 2 ** self.zoom
                tile_x = (x + max_tile) % max_tile
                tile_y = (y + max_tile) % max_tile
                url = self.url_template.format(z=self.zoom, x=tile_x, y=tile_y)
                tiles.append((x, y, url))

        thread_pool = ThreadPoolExecutor(4)

        for nb_retry in itertools.count():
            if not tiles:
                break
            if nb_retry > 0 and self.delay_between_retries:
                time.sleep(self.delay_between_retries)
            if nb_retry >= 3:
                raise RuntimeError(
                    f"Could not download {len(tiles)} map tiles after 3 attempts."
                )

            failed = []
            futures = [
                thread_pool.submit(self._get_tile, tile[2]) for tile in tiles
            ]
            for tile, future in zip(tiles, futures):
                x, y, url = tile
                try:
                    status, content = future.result()
                except Exception:
                    status, content = None, None

                if status != 200:
                    print(f"Tile request failed [{status}]: {url}")
                    failed.append(tile)
                    continue

                tile_image = Image.open(BytesIO(content)).convert("RGBA")
                box = [
                    self._x_to_px(x),
                    self._y_to_px(y),
                    self._x_to_px(x + 1),
                    self._y_to_px(y + 1),
                ]
                image.paste(tile_image, box, tile_image)

            tiles = failed

        return image

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(
        self,
        figsize=(12, 10),
        elev=30,
        azim=45,
        show_elevation=False,
        elevation_alpha=0.85,
        elevation_n_points=20,
        elevation_cmap="terrain",
        show_map=True,
        map_alpha=1.0,
        map_z=None,
        title=None,
        xlabel="Longitude",
        ylabel="Latitude",
        zlabel="Value",
        savefig=None,
        dpi=150,
    ):
        """
        Render the 3-D map and return ``(fig, ax)``.

        :param figsize: Matplotlib figure size in inches
        :type figsize: tuple
        :param elev: camera elevation angle in degrees
        :type elev: float
        :param azim: camera azimuth angle in degrees
        :type azim: float
        :param show_elevation: download SRTM elevation data and drape it as a
            surface cloth over the map
        :type show_elevation: bool
        :param elevation_alpha: opacity of the elevation surface (0–1)
        :type elevation_alpha: float
        :param elevation_n_points: grid resolution for the elevation surface
        :type elevation_n_points: int
        :param elevation_cmap: Matplotlib colormap for the elevation surface
            (only used when *show_map* is False)
        :type elevation_cmap: str
        :param show_map: drape the tile map image as a texture
        :type show_map: bool
        :param map_alpha: opacity of the flat map texture (0–1)
        :type map_alpha: float
        :param map_z: z position for the flat map plane; computed automatically
            when *None*
        :type map_z: float or None
        :param title: plot title
        :type title: str or None
        :param xlabel: x-axis label
        :type xlabel: str
        :param ylabel: y-axis label
        :type ylabel: str
        :param zlabel: z-axis label
        :type zlabel: str
        :param savefig: file path to save the figure; skipped when *None*
        :type savefig: str or None
        :param dpi: dots-per-inch for the saved figure
        :type dpi: int
        :return: ``(fig, ax)`` tuple
        :rtype: tuple
        """
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111, projection="3d")

        # ------ Gather z-range from overlay data ----------------------
        all_z = []
        for b in self._bars:
            all_z.extend(b["values"])
        for p in self._points:
            all_z.extend(p["values"])
        for ln in self._lines:
            all_z.extend(ln["values"])

        # ------ Elevation surface -------------------------------------
        LON_elev = LAT_elev = elevations = None
        if show_elevation:
            LON_elev, LAT_elev, elevations = self.fetch_elevation(elevation_n_points)
            all_z.extend([float(elevations.min()), float(elevations.max())])

        # ------ Map-plane z position ----------------------------------
        z_min = min(all_z) if all_z else 0.0
        z_max = max(all_z) if all_z else 1.0
        z_range = z_max - z_min or 1.0
        map_z_val = map_z if map_z is not None else z_min - z_range * 0.12

        # ------ Fetch tile image --------------------------------------
        map_image = None
        if show_map:
            map_image = self._fetch_map_image()

        # ------ Build map-image texture and draw surface --------------
        if show_elevation and LON_elev is not None:
            # Drape the map (or a colormap) over the elevation cloth
            if show_map and map_image is not None:
                img_arr = np.array(map_image)
                # Resize to elevation grid; flip vertically so lat increases upward
                img_resized = Image.fromarray(img_arr).resize(
                    (elevation_n_points, elevation_n_points), Image.LANCZOS
                )
                facecolors = np.flipud(np.array(img_resized)[:, :, :3] / 255.0)
                ax.plot_surface(
                    LON_elev,
                    LAT_elev,
                    elevations,
                    rstride=1,
                    cstride=1,
                    facecolors=facecolors,
                    alpha=elevation_alpha,
                    linewidth=0,
                    antialiased=True,
                    shade=False,
                )
            else:
                ax.plot_surface(
                    LON_elev,
                    LAT_elev,
                    elevations,
                    rstride=1,
                    cstride=1,
                    cmap=elevation_cmap,
                    alpha=elevation_alpha,
                    linewidth=0,
                    antialiased=True,
                )
        elif show_map and map_image is not None:
            # Flat map plane at map_z_val
            n_x = max(self.width // 8, 2)
            n_y = max(self.height // 8, 2)
            lons_grid = np.linspace(self.lon_min, self.lon_max, n_x)
            lats_grid = np.linspace(self.lat_min, self.lat_max, n_y)
            X_MAP, Y_MAP = np.meshgrid(lons_grid, lats_grid)
            Z_MAP = np.full_like(X_MAP, map_z_val)

            img_arr = np.array(map_image)
            img_resized = Image.fromarray(img_arr).resize((n_x, n_y), Image.LANCZOS)
            # Flip vertically: image row-0 = top (lat_max), but Y_MAP row-0 = lat_min
            facecolors = np.flipud(np.array(img_resized)[:, :, :3] / 255.0)
            ax.plot_surface(
                X_MAP,
                Y_MAP,
                Z_MAP,
                rstride=1,
                cstride=1,
                facecolors=facecolors,
                alpha=map_alpha,
                linewidth=0,
                antialiased=False,
                shade=False,
            )

        # ------ Bars --------------------------------------------------
        for bar_data in self._bars:
            w = bar_data["bar_width"]
            for (lon, lat), val in zip(bar_data["coords"], bar_data["values"]):
                ax.bar3d(
                    lon - w / 2,
                    lat - w / 2,
                    map_z_val,
                    w,
                    w,
                    val - map_z_val,
                    color=bar_data["color"],
                    alpha=bar_data["alpha"],
                    shade=True,
                )

        # ------ Scatter points ----------------------------------------
        for pt in self._points:
            xs = [c[0] for c in pt["coords"]]
            ys = [c[1] for c in pt["coords"]]
            ax.scatter(
                xs,
                ys,
                pt["values"],
                c=pt["color"],
                s=pt["size"],
                alpha=pt["alpha"],
                marker=pt["marker"],
                depthshade=True,
            )

        # ------ Lines -------------------------------------------------
        for ln in self._lines:
            xs = [c[0] for c in ln["coords"]]
            ys = [c[1] for c in ln["coords"]]
            ax.plot(
                xs,
                ys,
                ln["values"],
                color=ln["color"],
                linewidth=ln["width"],
                alpha=ln["alpha"],
            )

        # ------ Axis labels & ticks -----------------------------------
        ax.set_xlabel(xlabel, labelpad=8)
        ax.set_ylabel(ylabel, labelpad=8)
        ax.set_zlabel(zlabel, labelpad=8)

        # Show real lon/lat tick labels
        lon_ticks = np.linspace(self.lon_min, self.lon_max, 5)
        lat_ticks = np.linspace(self.lat_min, self.lat_max, 5)
        ax.set_xticks(lon_ticks)
        ax.set_xticklabels([f"{v:.2f}°" for v in lon_ticks], fontsize=7)
        ax.set_yticks(lat_ticks)
        ax.set_yticklabels([f"{v:.2f}°" for v in lat_ticks], fontsize=7)

        ax.view_init(elev=elev, azim=azim)

        if title:
            ax.set_title(title, pad=12)

        if savefig:
            fig.savefig(savefig, dpi=dpi, bbox_inches="tight")

        return fig, ax