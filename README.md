# pilot-image-processor

1. Build the image and give it a tag:
```sh
docker build . -t rasters
```

2. Run the image, mounting your image directory:
```sh
docker run -v <ABSOLUTE PATH TO IMAGE DIRECTORY>:/data/geotiff raster python3 prep_rasters.py
```

The image will expect a directory structure like:

- /
  - i01_Basemap
  - i02_Maps
  - i03_Plans
  - i04_Aerials

But any names are OK and the directory will be flattened when it is finished

Converted GeoTIFFs are exported to the `/converted/` directory. Generated rasters tiles are exported to the `/tiles/` directory.