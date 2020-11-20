"""Deal with raster transparency and convert to MBTiles for uploading"""

import os
import re
from string import Template
from shutil import copyfile, rmtree
from osgeo import gdal
import rasterio
import boto3

PATH = ''
s3 = boto3.client('s3')

def raster_bands(tif, sub):
  tif_file = PATH + sub + tif
  print('Reading raster', tif_file)
  try:
    src = gdal.Open(tif_file)
    ras = rasterio.open(tif_file)
  except:
    print('Cannot read', tif_file)
  
  else:
    val = ras.read(1)[0][0]

    if (src.RasterCount == 4 or (val != 0 and val != 255)) and ras.dtypes[0] == 'uint8':
      print('4 correct bands found')
      copyfile(tif_file, PATH + 'converted/' + tif)
      project_raster(tif)
    elif src.RasterCount == 1 or src.RasterCount == 3 or src.RasterCount == 4:
      gdal_string = Template("""gdal_translate -b 1 ${f} -a_nodata none ${path}converted/red.tif &&
          gdal_translate -b ${b2} ${f} -a_nodata none ${path}converted/green.tif &&
          gdal_translate -b ${b3} ${f} -a_nodata none ${path}converted/blue.tif &&
          echo Calculating file mask
          gdal_calc.py -A ${path}converted/red.tif -B ${path}converted/green.tif -C ${path}converted/blue.tif --outfile=${path}converted/mask.tif --calc="logical_and(A!=${nodata},B!=${nodata},C!=${nodata})*255" --NoDataValue=0 &&
          echo Merging files
          gdal_merge.py -separate -ot Byte -o ${path}converted/${tif} ${path}converted/red.tif ${path}converted/green.tif ${path}converted/blue.tif ${path}converted/mask.tif &&
          echo Cleaning up
          rm ${path}converted/red.tif &&
          rm ${path}converted/green.tif &&
          rm ${path}converted/blue.tif &&
          rm ${path}converted/mask.tif""")
      if src.RasterCount == 1:
        print('1 band raster found')
        os.system(gdal_string.substitute(f=tif_file, b2='1', b3='1', nodata=str(val),
                                          path=PATH, tif=tif))
        project_raster(tif)
      elif src.RasterCount >= 3:
        print('3+ band raster found')
        os.system(gdal_string.substitute(f=tif_file, b2='2', b3='3', nodata=str(val),
                                          path=PATH, tif=tif))
        project_raster(tif)
    else:
      print(tif_file + ' has wrong number of bands!')

def project_raster(tif):
  mb_string = Template("""gdal2tiles.py -s "EPSG:4326" -z "9-12"\
      --processes 8 -w none converted/${tif} tiles/""")
  os.system(mb_string.substitute(tif=tif))
  os.remove(os.path.join('converted', tif))
  uploadDirectory("tiles", re.sub(r"\.tif$", "", tif))

def uploadDirectory(path, ssid):
  for root, dirs, files in os.walk(path):
    for file in files:
      path = os.path.join(root, file)
      print('Uploading', path)
      s3.upload_file(path, os.environ['BUCKET_TARGET'], re.sub(r"tiles", ssid, path))
  rmtree('tiles', True)

images = s3.list_objects(Bucket=os.environ['BUCKET_SOURCE'])
for result in images['Contents']:
  key = result['Key']
  if re.search(r"\.tif$", key):
    file = re.sub(r".*\/(.*)", "\\1", key, re.IGNORECASE)
    with open(os.path.join("input", file), 'wb') as i:
      s3.download_fileobj(os.environ['BUCKET_SOURCE'], key, i)
      raster_bands(file, "input/")
    os.remove(os.path.join('input', file))
