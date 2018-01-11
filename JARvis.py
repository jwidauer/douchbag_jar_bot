import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
from telegram.error import TelegramError, Unauthorized, BadRequest, TimedOut, ChatMigrated, NetworkError
import logging
import speech_recognition as sr
import subprocess
import json
from enum import Enum

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

game_info = dict()
game_state = dict()

players = list()
usernames = list()
super_users = list()

def load_game():
    global game_info
    global game_state
    global players
    global usernames
    global super_users

    game_info = json.load(open('game_information.json', 'r'))
    game_state = json.load(open('game_state.json', 'r'))

    players = game_info['players']
    usernames = game_info['usernames']
    super_users = game_info['super_users']

    for idx, player_name in enumerate(players):
        if player_name not in game_state and idx < len(usernames):
            game_state[player_name]['score'] = 0
            game_state[player_name]['quotes'] = []
            game_state[player_name]['username'] = usernames[idx]

load_game()

class State(Enum):
    IDLE = 1
    WAIT_FOR_QUOTE = 2

current_state = State.IDLE

last_player = None
last_quote = None
tmp_quote = None

def authorized_user(update):
    for player_name in players:
        if game_state[player_name]['username'] == update.message.from_user.username :
            return True

    update.message.reply_text(text = "You're not playing. Go away!")
    print("Unauthorized user access.")
    return False

def start(bot, update):
    if authorized_user(update):
        update.message.reply_text(text="Let's collect some points!")


def add_points(bot, update, args):
    if authorized_user(update):
        global current_state
        if current_state == State.IDLE:
            if len(args) != 2:
                update.message.reply_text(text="You gotta send me a name and the points to add.")
                return
            try:
                name = args[0].lower()
                points = float(args[1])
            except:
                try:
                    name = args[1].lower()
                    points = float(args[0])
                except:
                    update.message.reply_text(text="None of the arguments is a number.")
                    return

            if name in game_state:
                game_state[name]['score'] += abs(points)
                msg = "Added " + str(points) + " points to " + name.title() + "s score.\n"
                msg += "What did " + name.title() + " say?"
                update.message.reply_text(text=msg)

                current_state = State.WAIT_FOR_QUOTE
                global last_player
                last_player = name
            else:
                msg = name.title() + " is not playing."
                update.message.reply_text(text=msg)

def add_player(bot, update, args):
    if update.message.from_user.username in super_users:
        if len(args) != 2:
            update.message.reply_text(text='Need player name and user to create user.')
            return

        game_info['players'].append(args[0])
        game_info['usernames'].append(args[1])

        json.dump(game_info, open('game_information.json', 'w'), indent=4, separators=(',', ': '))
        load_game()
        update.message.reply_text(text='Added ' + args[0] + ' to the game with username: ' + args[1])

def print_scores(bot, update):
    if authorized_user(update):
        if current_state == State.IDLE:
            msg = "Current scores are:\n\n"
            for player_name in players:
                msg += player_name.title() + ":  " + str(game_state[player_name]['score']) + "\n"
            if last_player != "":
                msg += "\nWith " + last_player.title() + " being the last one to receive points for saying: \n"
                msg += last_quote
            update.message.reply_text(text=msg)
        else:
            update.message.reply_text(text="Please tell me the quote first.")


def get_players(bot, update):
    if authorized_user(update):
        if current_state == State.IDLE:
            msg = "Current players are:\n"
            for player_name in players:
                msg += player_name.title() + "\n"
            update.message.reply_text(text=msg)
        else:
            update.message.reply_text(text="Please tell me the quote first.")

def get_quotes(bot, update, args):
    if authorized_user(update):
        if current_state == State.IDLE:
            if len(args) != 0:
                msg = "I have these quotes for the requested player/s:\n\n"
                for name in args:
                    if name.lower() in game_state:
                        msg += name + ":\n"
                        for quote in game_state[name]['quotes']:
                            msg += '"' + quote + '"\n'
                        msg += "\n"
                update.message.reply_text(text=msg)
            else:
                msg = "Showing all quotes for current players:\n\n"
                for name in players:
                    if name.lower() in game_state:
                        msg += name.title() + ":\n"
                        for quote in game_state[name]['quotes']:
                            msg += '"' + quote + '"\n'
                        msg += "\n"
                update.message.reply_text(text=msg)
        else:
            update.message.reply_text(text="Please tell me the quote first.")


def text_in(bot, update):
    if authorized_user(update):
        if current_state == State.WAIT_FOR_QUOTE:
            global tmp_quote
            tmp_quote = update.message.text
            keyboard = [[InlineKeyboardButton("\u2713", callback_data="True"),
                         InlineKeyboardButton("\u2717", callback_data="False")]]

            reply_keyboard = InlineKeyboardMarkup(keyboard)

            msg = "Did he really say:\n \u0022"
            msg += update.message.text + "\u0022?"
            update.message.reply_text(text=msg, reply_markup=reply_keyboard)


def convert_voice(bot, update):
    if authorized_user(update):
        if current_state == State.WAIT_FOR_QUOTE:
            file_id = update.message.voice.file_id
            newFile = bot.getFile(file_id)

            newFile.download('voice.ogg')
            command = ["ffmpeg", "-hide_banner", "-loglevel", "panic", "-i", 'voice.ogg', "-f", "wav", "-"]
            converter = subprocess.Popen(command, stdout=subprocess.PIPE)

            r = sr.Recognizer()
            with sr.AudioFile(converter.stdout) as source:
                audio = r.record(source)

            try:
                recognized_text = r.recognize_google(audio, language="de-DE")

                global tmp_quote
                tmp_quote = recognized_text
                keyboard = [[InlineKeyboardButton("\u2713", callback_data="True"),
                             InlineKeyboardButton("\u2717", callback_data="False")]]

                reply_keyboard = InlineKeyboardMarkup(keyboard)

                msg = "Did he really say:\n \u0022"
                msg += recognized_text + "\u0022?"
                update.message.reply_text(text=msg, reply_markup=reply_keyboard)
            except sr.UnknownValueError:
                update.message.reply_text(text="Could you repeat that?")
            except sr.RequestError as e:
                update.message.reply_text(
                    text="Could not request results from Google Speech Recognition service; {0}".format(e))


def button_callback(bot, update):
    query = update.callback_query
    global tmp_quote
    if query.data == "True" and tmp_quote != None:
        add_quote(tmp_quote)
        query.edit_message_text(text="Saved quote:\n" + tmp_quote)
    else:
        query.edit_message_text(text="Please tell me the right quote then.")

def unknown(bot, update):
    if authorized_user(update):
        update.message.reply_text(text="Sorry, I don't know that command.")

def add_quote(quote):
    global current_state
    if current_state == State.WAIT_FOR_QUOTE:
        if last_player != "":
            game_state[last_player]['quotes'].append(quote)
            global last_quote
            last_quote = quote
        with open('game_state.json','w') as outfile:
            json.dump(game_state, outfile, sort_keys=True, indent=4, separators=(',', ': '))
        global tmp_quote
        tmp_quote = None
        current_state = State.IDLE

def error_callback(bot, update, error):
    try:
        raise error
    except Unauthorized:
        print("Unauthorized error.")
        # remove update.message.chat_id from conversation list
    except BadRequest as e:
        print("Bad request error: " + e.message)
        # handle malformed requests - read more below!
    except TimedOut:
        print("Timed out error.")
        # handle slow connection problems
    except NetworkError:
        print("Network error.")
        # handle other connection problems
    except ChatMigrated as e:
        print("Chat migrated as: " + e)
        # the chat_id of a group has changed, use e.new_chat_id instead
    except TelegramError:
        print("Something else error.")
        # handle all other telegram related errors

bot = telegram.Bot(token=game_info['token'])
updater = Updater(token=game_info['token'])
dispatcher = updater.dispatcher

button_handler = CallbackQueryHandler(button_callback)

start_handler = CommandHandler('start', start)
add_pts_handler = CommandHandler('add', add_points, pass_args=True)
score_handler = CommandHandler('score', print_scores)
player_handler = CommandHandler('players', get_players)
quotes_handler = CommandHandler('quotes', get_quotes, pass_args=True)
add_player_handler = CommandHandler('add_player', add_player, pass_args=True)

text_handler = MessageHandler(Filters.text, text_in)
voice_handler = MessageHandler(Filters.voice, convert_voice)
unknown_handler = MessageHandler(Filters.command, unknown)

dispatcher.add_handler(button_handler)

dispatcher.add_handler(start_handler)
dispatcher.add_handler(add_pts_handler)
dispatcher.add_handler(score_handler)
dispatcher.add_handler(player_handler)
dispatcher.add_handler(quotes_handler)
dispatcher.add_handler(add_player_handler)

dispatcher.add_handler(text_handler)
dispatcher.add_handler(voice_handler)

dispatcher.add_handler(unknown_handler)
dispatcher.add_error_handler(error_callback)

updater.start_polling()
updater.idle()