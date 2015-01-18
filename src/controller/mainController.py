# -*- coding: utf-8 -*-
from wxUI import (view, dialogs, commonMessageDialogs)
import buffersController
import messages
from sessionmanager import session as session_
from pubsub import pub
import sound
import output
from twython import TwythonError
from mysc.thread_utils import call_threaded
from mysc.repeating_timer import RepeatingTimer
import config
import widgetUtils
import platform
from extra import SoundsTutorial
import logging
if platform.system() == "Windows":
 import keystrokeEditor

log = logging.getLogger("mainController")

class Controller(object):

 """ Main Controller for TWBlue. It manages the main window and sessions."""

 def search_buffer(self, name_, user):

  """ Searches a buffer.
 name_ str: The name for the buffer
 user str: The account for the buffer.
 for example you may want to search the home_timeline buffer for the tw_blue2 user.
  returns buffersController.buffer object with the result if there is one."""
  for i in self.buffers:
   if i.name == name_ and i.account == user: return i

 def get_current_buffer(self):
  buffer = self.view.get_current_buffer()
  if hasattr(buffer, "account"):
   buffer = self.search_buffer(buffer.name, buffer.account)
   return buffer

 def get_best_buffer(self):
  # Gets the parent buffer to know what account is doing an action
  view_buffer = self.view.get_current_buffer()
  # If the account has no session attached, we will need to search the home_timeline for that account to use its session.
  if view_buffer.type == "account" or view_buffer.type == "empty":
   buffer = self.search_buffer("home_timeline", view_buffer.account)
  else:
   buffer = self.search_buffer(view_buffer.name, view_buffer.account)
  return buffer

 def bind_stream_events(self):
  log.debug("Binding events for the Twitter stream API...")
  pub.subscribe(self.manage_home_timelines, "item-in-home")
  pub.subscribe(self.manage_mentions, "mention")
  pub.subscribe(self.manage_direct_messages, "direct-message")
  pub.subscribe(self.manage_sent_dm, "sent-dm")
  pub.subscribe(self.manage_sent_tweets, "sent-tweet")
  pub.subscribe(self.manage_events, "event")
  pub.subscribe(self.manage_followers, "follower")
  pub.subscribe(self.manage_friend, "friend")
  pub.subscribe(self.manage_unfollowing, "unfollowing")
  pub.subscribe(self.manage_favourite, "favourite")
  pub.subscribe(self.manage_unfavourite, "unfavourite")
  pub.subscribe(self.manage_blocked_user, "blocked-user")
  pub.subscribe(self.manage_unblocked_user, "unblocked-user")
  pub.subscribe(self.manage_item_in_timeline, "item-in-timeline")
  widgetUtils.connect_event(self.view, widgetUtils.CLOSE_EVENT, self.exit)

 def bind_other_events(self):
  log.debug("Binding other application events...")
  pub.subscribe(self.editing_keystroke, "editing_keystroke")
  pub.subscribe(self.manage_stream_errors, "stream-error")
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.search, menuitem=self.view.menuitem_search)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.learn_sounds, menuitem=self.view.sounds_tutorial)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.exit, menuitem=self.view.close)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.post_tweet, self.view.compose)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.post_reply, self.view.reply)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.post_retweet, self.view.retweet)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.add_to_favourites, self.view.fav)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.remove_from_favourites, self.view.unfav)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.view_item, self.view.view)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.delete, self.view.delete)
  widgetUtils.connect_event(self.view, widgetUtils.MENU, self.send_dm, self.view.dm)

 def __init__(self):
  super(Controller, self).__init__()
  self.view = view.mainFrame()
  self.buffers = []
  self.view.prepare()
  self.bind_stream_events()
  self.bind_other_events()
  self.do_work()

 def do_work(self):
  log.debug("Creating buffers for all sessions...")
  for i in session_.sessions:
   log.debug("Working on session %s" % (i,))
   self.create_buffers(session_.sessions[i])
   call_threaded(self.start_buffers, session_.sessions[i])
  sound.player.play("tweet_timeline.ogg")
  self.checker_function = RepeatingTimer(60, self.check_connection)
  self.checker_function.start()

 def create_buffers(self, session):
  session.get_user_info()
  account = buffersController.accountPanel(self.view.nb, session.db["user_name"], session.db["user_name"])
  self.buffers.append(account)
  self.view.add_buffer(account.buffer , name=session.db["user_name"])
  home = buffersController.baseBufferController(self.view.nb, "get_home_timeline", "home_timeline", session, session.db["user_name"])
  self.buffers.append(home)
  self.view.insert_buffer(home.buffer, name=_(u"Home"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  mentions = buffersController.baseBufferController(self.view.nb, "get_mentions_timeline", "mentions", session, session.db["user_name"])
  self.buffers.append(mentions)
  self.view.insert_buffer(mentions.buffer, name=_(u"Mentions"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  sound.player.play("mention_received.ogg")
  dm = buffersController.baseBufferController(self.view.nb, "get_direct_messages", "direct_messages", session, session.db["user_name"], bufferType="dmPanel")
  self.buffers.append(dm)
  self.view.insert_buffer(dm.buffer, name=_(u"Direct messages"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  sound.player.play("dm_received.ogg")
  sent_dm = buffersController.baseBufferController(self.view.nb, "get_sent_messages", "sent_direct_messages", session, session.db["user_name"], bufferType="dmPanel")
  self.buffers.append(sent_dm)
  self.view.insert_buffer(sent_dm.buffer, name=_(u"Sent direct messages"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  sent_tweets = buffersController.baseBufferController(self.view.nb, "get_user_timeline", "sent_tweets", session, session.db["user_name"], bufferType="dmPanel", screen_name=session.db["user_name"])
  self.buffers.append(sent_tweets)
  self.view.insert_buffer(sent_tweets.buffer, name=_(u"Sent tweets"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  if session.settings["other_buffers"]["show_favourites"] == True:
   favourites = buffersController.baseBufferController(self.view.nb, "get_favorites", "favourites", session, session.db["user_name"])
   self.buffers.append(favourites)

   self.view.insert_buffer(favourites.buffer, name=_(u"Favourites"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  if session.settings["other_buffers"]["show_followers"] == True:
   followers = buffersController.peopleBufferController(self.view.nb, "get_followers_list", "followers", session, session.db["user_name"], screen_name=session.db["user_name"])
   self.buffers.append(followers)
   self.view.insert_buffer(followers.buffer, name=_(u"Followers"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  if session.settings["other_buffers"]["show_friends"] == True:
   friends = buffersController.peopleBufferController(self.view.nb, "get_friends_list", "friends", session, session.db["user_name"], screen_name=session.db["user_name"])
   self.buffers.append(friends)
   self.view.insert_buffer(friends.buffer, name=_(u"Friends"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  if session.settings["other_buffers"]["show_blocks"] == True:
   blocks = buffersController.peopleBufferController(self.view.nb, "list_blocks", "blocked", session, session.db["user_name"])
   self.buffers.append(blocks)
   self.view.insert_buffer(blocks.buffer, name=_(u"Blocked users"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  if session.settings["other_buffers"]["show_muted_users"] == True:
   muted = buffersController.peopleBufferController(self.view.nb, "get_muted_users_list", "muted", session, session.db["user_name"])
   self.buffers.append(muted)
   self.view.insert_buffer(muted.buffer, name=_(u"Muted users"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  if session.settings["other_buffers"]["show_events"] == True:
   events = buffersController.eventsBufferController(self.view.nb, "events", session, session.db["user_name"], bufferType="dmPanel", screen_name=session.db["user_name"])
   self.buffers.append(events)
   self.view.insert_buffer(events.buffer, name=_(u"Events"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  timelines = buffersController.emptyPanel(self.view.nb, "timelines", session.db["user_name"])
  self.buffers.append(timelines)
  self.view.insert_buffer(timelines.buffer , name=_(u"Timelines"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  for i in session.settings["other_buffers"]["timelines"]:
   tl = buffersController.baseBufferController(self.view.nb, "get_user_timeline", "%s-timeline" % (i,), session, session.db["user_name"], bufferType=None, screen_name=i)
   self.buffers.append(tl)
   self.view.insert_buffer(tl.buffer, name=_(u"Timeline for {}".format(i)), pos=self.view.search("timelines", session.db["user_name"]))
  searches = buffersController.emptyPanel(self.view.nb, "searches", session.db["user_name"])
  self.buffers.append(searches)
  self.view.insert_buffer(searches.buffer , name=_(u"Searches"), pos=self.view.search(session.db["user_name"], session.db["user_name"]))
  for i in session.settings["other_buffers"]["tweet_searches"]:
   tl = buffersController.searchBufferController(self.view.nb, "search", "%s-searchterm" % (i,), session, session.db["user_name"], bufferType="searchPanel", q=i)
   self.buffers.append(tl)
   self.view.insert_buffer(tl.buffer, name=_(u"Search for {}".format(i)), pos=self.view.search("searches", session.db["user_name"]))
   tl.timer = RepeatingTimer(180, tl.start_stream)
   tl.timer.start()

 def search(self, *args, **kwargs):
  log.debug("Creating a new search...")
  dlg = dialogs.search.searchDialog()
  if dlg.get_response() == widgetUtils.OK:
   term = dlg.get("term")
   buffer = self.get_best_buffer()
   if dlg.get("tweets") == True:
    if term not in buffer.session.settings["other_buffers"]["tweet_searches"]:
     buffer.session.settings["other_buffers"]["tweet_searches"].append(term)
     search = buffersController.searchBufferController(self.view.nb, "search", "%s-searchterm" % (term,), buffer.session, buffer.session.db["user_name"], bufferType="searchPanel", q=term)
    else:
     log.error("A buffer for the %s search term is already created. You can't create a duplicate buffer." % (term,))
     return
   elif dlg.get("users") == True:
    search = buffersController.searchPeopleBufferController(self.view.nb, "search_users", "%s-searchUser" % (term,), buffer.session, buffer.session.db["user_name"], bufferType=None, q=term)
   self.buffers.append(search)
   search.start_stream()
   self.view.insert_buffer(search.buffer, name=_(u"Search for {}".format(term)), pos=self.view.search("searches", buffer.session.db["user_name"]))
   search.timer = RepeatingTimer(180, search.start_stream)
   search.timer.start()
  dlg.Destroy()

 def edit_keystrokes(self, event=None):
  dlg = keystrokeEditor.keystrokeEditor()
  dlg.put_keystrokes(**config.app["keymap"])
  dlg.ShowModal()
  dlg.Destroy()

 def learn_sounds(self, *args, **kwargs):
  SoundsTutorial.soundsTutorial()

 def view_user_lists(self, users):
  pass

 def add_to_list(self, user):
  pass

 def remove_from_list(self, user):
  pass

 def lists_manager(self):
  pass

 def configuration(self):
  pass

 def update_profile(self):
  pass

 def show_document(self, document):
  pass

 def report_error(self):
  pass

 def check_for_updates(self, show_msg=True):
  pass

 def show_details_for_user(self, user):
  pass

 def delete(self, *args, **kwargs):
  buffer = self.view.get_current_buffer()
  if hasattr(buffer, "account"):
   buffer = self.search_buffer(buffer.name, buffer.account)
   buffer.destroy_status()

 def exit(self, *args, **kwargs):
  log.debug("Exiting...")
  for item in session_.sessions:
   log.debug("Saving config for %s session" % (session_.sessions[item].session_id,))
   session_.sessions[item].settings.write()
   log.debug("Disconnecting streams for %s session" % (session_.sessions[item].session_id,))
   session_.sessions[item].main_stream.disconnect()
   session_.sessions[item].timelinesStream.disconnect()
  sound.player.cleaner.cancel()
  widgetUtils.exit_application()

 def action(self, do_action):
  pass

 def post_tweet(self, event=None):
  buffer = self.get_best_buffer()
  buffer.post_tweet()

 def post_reply(self, *args, **kwargs):
  buffer = self.get_current_buffer()
  if buffer.name == "sent_direct_messages" or buffer.name == "sent-tweets": return
  elif buffer.name == "direct_messages":
   buffer.direct_message()
  else:
   buffer.reply()

 def send_dm(self, user):
  buffer = self.get_current_buffer()
  if buffer.name == "sent_direct_messages" or buffer.name == "sent-tweets": return
  else:
   buffer.direct_message()

 def post_retweet(self, *args, **kwargs):
  buffer = self.get_current_buffer()
  if buffer.type == "dm" or buffer.type == "people" or buffer.type == "events":
   return
  else:
   buffer.retweet()

 def add_to_favourites(self, *args, **kwargs):
  buffer = self.get_current_buffer()
  if buffer.type == "dm" or buffer.type == "people" or buffer.type == "events":
   return
  else:
   id = buffer.get_tweet()["id"]
   call_threaded(buffer.session.api_call, call_name="create_favorite", _sound="favourite.ogg", id=id)

 def remove_from_favourites(self, *args, **kwargs):
  buffer = self.get_current_buffer()
  if buffer.type == "dm" or buffer.type == "people" or buffer.type == "events":
   return
  else:
   id = buffer.get_tweet()["id"]
   call_threaded(buffer.session.api_call, call_name="destroy_favorite", id=id)

 def view_item(self, *args, **kwargs):
  buffer = self.get_current_buffer()
  if buffer.type == "baseBuffer" or buffer.type == "favourites_timeline" or buffer.type == "list" or buffer.type == "search":
   try:
    tweet = buffer.get_right_tweet()
    msg = messages.viewTweet(tweet, )
   except TwythonError:
    non_tweet = buffer.get_message()
    msg = messages.viewTweet(non_tweet, False)
  elif buffer.type == "account" or buffer.type == "empty":
   return
  else:
   non_tweet = buffer.get_message()
   msg = messages.viewTweet(non_tweet, False)

 def open_timeline(self, user, timeline_tipe):
  pass

 def remove_buffer(self):
  pass

 def show_hide(self):
  pass

 def toggle_global_mute(self):
  pass

 def toggle_mute(self):
  pass

 def toggle_autoread(self):
  pass

 def go_conversation(self, orientation):
  pass

 def notify(self, play_sound=None, message=None, notification=False):
  if play_sound != None:
   sound.player.play(play_sound)
  if message != None:
   output.speak(message)

 def manage_home_timelines(self, data, user):
  buffer = self.search_buffer("home_timeline", user)
  play_sound = "tweet_received.ogg"
  buffer.add_new_item(data)
  self.notify(play_sound=play_sound)

 def manage_mentions(self, data, user):
  buffer = self.search_buffer("mentions", user)
  play_sound = "mention_received.ogg"
  buffer.add_new_item(data)
  message = _(u"New mention")
  self.notify(play_sound=play_sound, message=message)

 def manage_direct_messages(self, data, user):
  buffer = self.search_buffer("direct_messages", user)
  play_sound = "dm_received.ogg"
  buffer.add_new_item(data)
  message = _(u"New direct message")
  self.notify(play_sound=play_sound, message=message)

 def manage_sent_dm(self, data, user):
  buffer = self.search_buffer("sent_direct_messages", user)
  play_sound = "dm_sent.ogg"
  buffer.add_new_item(data)
  self.notify(play_sound=play_sound)

 def manage_sent_tweets(self, data, user):
  buffer = self.search_buffer("sent_tweets", user)
  play_sound = "tweet_send.ogg"
  buffer.add_new_item(data)
  self.notify(play_sound=play_sound)

 def manage_events(self, data, user):
  buffer = self.search_buffer("events", user)
  play_sound = "new_event.ogg"
  buffer.add_new_item(data)
  self.notify(play_sound=play_sound)

 def manage_followers(self, data, user):
  buffer = self.search_buffer("followers", user)
  play_sound = "update_followers.ogg"
  buffer.add_new_item(data)
  self.notify(play_sound=play_sound)

 def manage_friend(self, data, user):
  buffer = self.search_buffer("friends", user)
  buffer.add_new_item(data)

 def manage_unfollowing(self, item, user):
  buffer = self.search_buffer("friends", user)
  play_sound = "new_event.ogg"
  buffer.remove_item(item)

 def manage_favourite(self, data, user):
  buffer = self.search_buffer("favourites", user)
  play_sound = "favourite.ogg"
  buffer.add_new_item(data)
  self.notify(play_sound=play_sound)

 def manage_unfavourite(self, item, user):
  buffer = self.search_buffer("favourites", user)
  buffer.remove_item(item)

 def manage_blocked_user(self, data, user):
  buffer = self.search_buffer("blocked", user)
  buffer.add_new_item(data)

 def manage_unblocked_user(self, item, user):
  buffer = self.search_buffer("blocked", user)
  buffer.remove_item(item)

 def manage_item_in_timeline(self, data, user, who):
  buffer = self.search_buffer("%s-timeline" % (who,), user)
  play_sound = "tweet_timeline.ogg"
  buffer.add_new_item(data)
  self.notify(play_sound=play_sound)

 def editing_keystroke(self, action, parentDialog):
  print "i've pressed"

 def start_buffers(self, session):
  log.debug("starting buffers... Session %s" % (session.session_id,))
  for i in self.buffers:
   if i.session == session and i.needs_init == True:
    i.start_stream()
  log.debug("Starting the streaming endpoint")
  session.start_streaming()

 def manage_stream_errors(self, session):
  log.error("An error ocurred with the stream for the %s session. It will be destroyed" % (session,))
  s = sessions_.session[session]
  s.listen_stream_error()

 def check_connection(self):
  for i in session_.sessions:
   session_.sessions[i].check_connection()

 def __del__(self):
  config.app.write()