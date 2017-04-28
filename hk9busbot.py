#!/usr/bin/env python
# -*- coding: utf-8 -*-
#https://github.com/python-telegram-bot/python-telegram-bot/wiki/Performance-Optimizations

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram.error import (TelegramError, Unauthorized, BadRequest, TimedOut, ChatMigrated, NetworkError)
from telegram.ext.dispatcher import run_async
from urllib3.exceptions import ReadTimeoutError
import json
import requests
from datetime import datetime
import re

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
					level=logging.INFO)

@run_async
def start(bot, update):
	return print(update)
	bot.sendMessage(chat_id=update.message.chat_id, text="Hi. Send個九巴巴士No.來")

@run_async
def search(bot, update):
	return print(update)
	group_chat = True if update.message.chat_id < 0 else False
	if(group_chat):
		if("9bus" not in update.message.text):
			return
		update.message.text = update.message.text.replace("9bus","").strip()
	route = update.message.text.upper()
	if not re.search(r'[A-Z]*[0-9]+[A-Z]*',route):
		return update.message.reply_text('invalid bus number')
	print("%s search %s"%(update.message.from_user.first_name,route))

	try:
		r = requests.get("http://search.kmb.hk/KMBWebSite/Function/FunctionRequest.ashx?action=getstops&route=%s&bound=1&serviceType=1"%route, headers={'Connection':'close'})
		data = json.loads(r.text.replace("\ue473","邨"))
		OriCName = data["data"]["basicInfo"]["OriCName"]
		DestCName = data["data"]["basicInfo"]["DestCName"]
		r = requests.get("http://search.kmb.hk/KMBWebSite/Function/FunctionRequest.ashx?action=getroutebound&route=%s"%route)
		data = json.loads(r.text)
		bound = set()
		for d in data["data"]:
			bound.add(d["BOUND"])
		if (len(bound) == 1):
			keyboard = [[InlineKeyboardButton(OriCName, callback_data="route=%s&bound=1"%route)],[InlineKeyboardButton(DestCName, callback_data="route=%s&bound=1"%route)]]
		else:
			keyboard = [[InlineKeyboardButton(OriCName, callback_data="route=%s&bound=2"%route)],[InlineKeyboardButton(DestCName, callback_data="route=%s&bound=1"%route)]]
		reply_markup = InlineKeyboardMarkup(keyboard)
		update.message.reply_text('往駛方向:', reply_markup=reply_markup)
	except Exception as e:
		print(type(e).__name__)
		print(str(e))

@run_async
def button(bot, update):
	return print(update)
	getTime = False
	query = update.callback_query
	try:
		if ("close" in query.data):
			bot.editMessageText(text=":)",
					chat_id=query.message.chat_id,
					message_id=query.message.message_id)
			return
		tokens = query.data.split("&")
		for token in tokens:
			if("route" in token):
				route = token.split("=")[1]
			if("bound" in token):
				bound = token.split("=")[1]
			if("bsiCode" in token):
				bsiCode = token.split("=")[1]
				getTime = True
			if("seq" in token):
				seq = token.split("=")[1]
		print("%s refresh %s" % (query.message.chat.first_name, route))#query.message.from_user
		if(getTime):
			#get direction, seq name
			r = requests.get("http://search.kmb.hk/KMBWebSite/Function/FunctionRequest.ashx?action=getstops&route=%s&bound=%s&serviceType=1"%(route,bound), headers={'Connection':'close'})
			data = json.loads(r.text.replace("\ue473","邨"))
			OriCName = data["data"]["basicInfo"]["OriCName"]
			DestCName = data["data"]["basicInfo"]["DestCName"]
			station = data["data"]["routeStops"][int(seq)]["CName"]

			#get the time
			link = "http://search.kmb.hk/KMBWebSite/Function/FunctionRequest.ashx/?action=geteta&lang=1&route=%s&bound=%s&servicetype=1&bsiCode=%s&seq=%s"%(route,bound,bsiCode,seq)
			r = requests.get(link)
			data = json.loads(r.text)
			text = "巴士%s【%s】\n%s==>%s\n"%(route,station,OriCName,DestCName)
			last_update = datetime.fromtimestamp(int(data["data"]["updated"])/1000).strftime('%H:%M:%S')

			for t in data["data"]["response"]:
				time_diff = cal_time_diff(t["t"])
				if(time_diff != -999):
					text += "<b>(%d分鐘)</b>　"%time_diff + t["t"] + "\n"
				else:
					text += t["t"] + "\n"
			text += "<i>[資料時間: %s]</i>"%last_update
			bot.editMessageText(text=text,
							chat_id=query.message.chat_id,
							message_id=query.message.message_id,
							reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("F5",callback_data="route=%s&bound=%s&bsiCode=%s&seq=%s"%(route,bound,bsiCode,seq))]]),
							parse_mode="HTML")
			return

		#get the station names
		r = requests.get("http://search.kmb.hk/KMBWebSite/Function/FunctionRequest.ashx?action=getstops&route=%s&bound=%s&serviceType=1"%(route,bound), headers={'Connection':'close'})
		data = json.loads(r.text.replace("\ue473","邨"))
		#print(data["data"])
		stations = list()
		for station in data["data"]["routeStops"]:
			#print(station["CName"])
			stations.append([InlineKeyboardButton(station["CName"],callback_data="route=%s&bound=%s&bsiCode=%s&seq=%s"%(route,bound,station["BSICode"],station["Seq"]))])
		stations.append([InlineKeyboardButton("Close", callback_data="close")])
		reply_markup = InlineKeyboardMarkup(stations)
		bot.editMessageText(text="現在車站:",
							chat_id=query.message.chat_id,
							message_id=query.message.message_id,
							reply_markup=reply_markup)
	except Exception as e:
		print(str(e))

@run_async
def help(bot, update):
	update.message.reply_text("see @herolun")

@run_async
def error(bot, update, error):
	logging.warning('Update "%s" caused error "%s"' % (update, error))

@run_async
def error_callback(bot, update, error):
	try:
		raise error
	except BadRequest:
		return
	#see more https://github.com/python-telegram-bot/python-telegram-bot/wiki/Exception-Handling

def cal_time_diff(time_str):
	try:
		cur_time = datetime.now().strftime('%H:%M:%S')
		hr = int(time_str.split(":")[0])
		minute = int(time_str.split(":")[1].split("　")[0])

		cur_hr = int(cur_time.split(":")[0])
		cur_minute = int(cur_time.split(":")[1])
		cur_sec = int(cur_time.split(":")[2])
		offset = 1 if cur_sec>30 else 0

		if(hr - cur_hr < 0):#if 00:31 arrive vs current 23:20
			hr += 24
		min_diff = (hr - cur_hr)*60 + minute - cur_minute
		if(min_diff > 0):
			min_diff -= offset
	except Exception:
		min_diff = -999
	finally:
		return min_diff


# Create the Updater and pass it your bot's token.
updater = Updater(YOUR_BOT_TOKEN_HERE, workers=64)

updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(MessageHandler(Filters.text, search))
updater.dispatcher.add_handler(CallbackQueryHandler(button))
updater.dispatcher.add_handler(CommandHandler('help', help))
#updater.dispatcher.add_error_handler(error)
updater.dispatcher.add_error_handler(error_callback)

# Start the Bot
while (True):
	try:
		updater.start_polling()
		# Run the bot until the user presses Ctrl-C or the process receives SIGINT,
		# SIGTERM or SIGABRT
		updater.idle()
	except ReadTimeoutError:
		continue
