from distutils.core import setup

setup(
    name='staticmap',
    packages=['staticmap', 'staticmap.plots'],
    version='0.6.0',
    description='A python library for creating static and 3D map plots with lines, markers and elevation data.',
    author='Christoph Lingg',
    author_email='christoph@komoot.de',
    url='https://github.com/komoot/staticmap',
    download_url='https://github.com/komoot/staticmap/tarball/0.1',
    keywords='static map image osm 3d elevation',
    classifiers=[],
    install_requires=[
        'Pillow',
        'requests',
        'numpy',
        'matplotlib',
        'futures;python_version<"3.2"'
    ]
)
