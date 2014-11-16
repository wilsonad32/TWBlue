# -*- coding: utf-8 -*-
from twitter import compose
from twython import TwythonStreamer
from pubsub import pub
import logging as original_logger
log = original_logger.getLogger("MainStream")

class timelinesStreamer(TwythonStreamer):
 def __init__(self, app_key, app_secret, oauth_token, oauth_token_secret, timeout=300, retry_count=None, retry_in=10, client_args=None, handlers=None, chunk_size=1, session=None):
  self.session = session
  super(timelinesStreamer, self).__init__(app_key, app_secret, oauth_token, oauth_token_secret, timeout=60, retry_count=None, retry_in=180, client_args=None, handlers=None, chunk_size=1)

 def on_error(self, status_code, data):
  log.debug("%s: %s" % (status_code, data))

 def check_tls(self, data):
  for i in self.session.settings["other_buffers"]["timelines"]:
   if data["user"]["screen_name"] == i:
    pub.sendMessage("item-in-timeline", data= data, user= self.session.db["user_name"], who= i)

 def on_success(self, data):
#  try:
  if "text" in data:
   self.check_tls(data)
#  except:
#   pass
 
class listsStreamer(timelinesStreamer):

 def on_success(self, data):
  try:
   if "text" in data:
    pub.sendMessage("item-in-list", **{"data": data, "user": self.session.db["user_name"]})
  except:
   pass