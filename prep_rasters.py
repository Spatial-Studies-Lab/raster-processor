"""Deal with raster transparency and convert to MBTiles for uploading"""

import os
import re
import time
import logging
from string import Template
from shutil import copyfile, rmtree
from osgeo import gdal
import rasterio
import boto3
from cloudwatch import cloudwatch
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger('logger')
formatter = logging.Formatter('%(asctime)s : %(levelname)s - %(message)s')
handler = cloudwatch.CloudwatchHandler(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'], 'us-east-1', 'raster-processor', str(round(time.time() * 1000)))
handler.setFormatter(formatter)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

def error_email(message):
  message = Mail(
    from_email='info@axismaps.com',
    to_emails=os.environ['EMAIL'],
    subject='GENERATOR ERROR: ' + os.environ['PROJECT'] + ' - ' + os.environ['TASK'],
    plain_text_content=message)
  try:
    sg = SendGridAPIClient(os.environ['SENDGRID_API_KEY'])
    response = sg.send(message)
    logger.info(response.status_code)
    logger.info(response.body)
    logger.info(response.headers)
  except Exception as e:
    print(e.message)
    logger.warning(e.message)

PATH = ''
s3 = boto3.client('s3')

def raster_bands(tif, sub, key):
  tif_file = PATH + sub + tif
  print('Reading raster', tif_file)
  logger.info('Reading raster ' + tif_file)
  try:
    src = gdal.Open(tif_file)
    ras = rasterio.open(tif_file)
    val = ras.read(1)[0][0]
  except:
    print('Cannot read', tif_file)
    logger.warning('Cannot read ' + tif_file, level="WARN")
    error_email('Cannot read ' + tif_file)
  
  else:
    # epsg = int(gdal.Info(src, format='json')['coordinateSystem']['wkt'].rsplit('"EPSG","', 1)[-1].split('"')[0])
    # if epsg == 4326:
    if (src.RasterCount == 4 or (val != 0 and val != 255)) and ras.dtypes[0] == 'uint8':
      print('4 correct bands found')
      logger.info('4 correct bands found')
      print('COPY START')
      copyfile(tif_file, PATH + 'converted/' + tif)
      print('COPY END')
      project_raster(tif, key)
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
        logger.info('1 band raster found')
        os.system(gdal_string.substitute(f=tif_file, b2='1', b3='1', nodata=str(val),
                                          path=PATH, tif=tif))
        project_raster(tif, key)
      elif src.RasterCount >= 3:
        print('3+ band raster found')
        logger.info('3+ band raster found')
        os.system(gdal_string.substitute(f=tif_file, b2='2', b3='3', nodata=str(val),
                                          path=PATH, tif=tif))
        project_raster(tif, key)
    else:
      print(tif_file + ' has wrong number of bands!')
      logger.warning(tif_file + ' has wrong number of bands', level="WARN")
      error_email(tif_file + ' has wrong number of bands')

def project_raster(tif, key):
  print('CREATING TILES')
  mb_string = Template("""gdal2tiles.py -s "EPSG:4326" -z "6-18"\
      --processes=8 -w none converted/${tif} tiles/""")
  print(mb_string.substitute(tif=tif))
  os.system(mb_string.substitute(tif=tif))
  os.remove(os.path.join('converted', tif))
  uploadDirectory("tiles", re.sub(r"\.tif$", "", tif), key)

def uploadDirectory(path, ssid, key):
  logger.info('Uploading ' + path)
  upload_string = Template("""aws s3 cp ${path} s3://${bucket}/${ssid} --recursive""")
  print(upload_string.substitute(path=path, bucket=os.environ['BUCKET_TARGET'], ssid=ssid))
  os.system(upload_string.substitute(path=path, bucket=os.environ['BUCKET_TARGET'], ssid=ssid))
  rmtree('tiles', True)
  print('Copy to completed')
  s3.copy_object(CopySource={'Bucket': os.environ['BUCKET_SOURCE'], 'Key': key}, Bucket=os.environ['BUCKET_SOURCE'], Key='completed/' + key)
  print('Delete original')
  s3.delete_object(Bucket=os.environ['BUCKET_SOURCE'], Key=key)

print('LISTING OBJECTS FROM SOURCE BUCKET')
images = s3.list_objects(Bucket=os.environ['BUCKET_SOURCE'])
for result in images['Contents']:
  key = result['Key']
  if re.search(r"\.tif$", key) and not re.search(r"(completed|error)", key):
    print('*** Processing', key)
    file = re.sub(r".*\/(.*)", "\\1", key, re.IGNORECASE)
    with open(os.path.join("input", file), 'wb') as i:
      s3.download_fileobj(os.environ['BUCKET_SOURCE'], key, i)
      raster_bands(file, "input/", key)
      os.remove(os.path.join('input', file))
