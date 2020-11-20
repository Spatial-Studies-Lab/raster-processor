
import json
import sys
import boto3
import time

# boto3 client
logs = boto3.client('logs')

# Define log group and log stream.  Default log group for glue logs and logstream defined dynamically upon job run.
log_group = "raster-processor"
log_stream = str(round(time.time() * 1000))
logs.create_log_stream(logGroupName=log_group, logStreamName=log_stream)

# Grab current time in milliseconds since Jan 1, 1970 00:00:00 UTC for use in cloudwatch put_log_events
def current_milli_time(): return int(round(time.time() * 1000))

# Functions
# Grabs next sequence token
def get_sequence_token():
  response = logs.describe_log_streams(
      logGroupName=log_group,
      logStreamNamePrefix=log_stream
  )
  print(response)
  next_token = response['logStreams'][0]["uploadSequenceToken"]
  return next_token

# Actually puts the event
def put_event(msg):
  # NOTE: This should only be called from send_msg()
  next_token = get_sequence_token()

  response_put = logs.put_log_events(
    logGroupName=log_group,
    logStreamName=log_stream,
    logEvents=[
      {
        'timestamp': current_milli_time(),
        'message': msg
      }
    ]
  )

  print(response_put)

# Provides interface for put_events, change default loglevel here
def send_msg(msg, level="INFO"):
  # Generate timestamp for the header
  timestamp = time.strftime("%y/%m/%d %H:%M:%S", time.gmtime())

  # Customize header here
  put_event(timestamp + " " + level + " " + msg)


# example log string/object provided
json_object = {
  "message": "Init logs"
}

send_msg(json.dumps(json_object))
