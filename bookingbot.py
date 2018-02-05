import datetime
from calendar import monthrange

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import (TimedOut, NetworkError)

import dateutil
import filters
from datacore import *
from dispatcher import *

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

adm = [#155247459,
    153174359]

time_rows = 5


def book(bot, update):
    repository.purge_user(update.message.chat_id)
    next_few = dateutil.get_next_few_months()
    month_keys = [[InlineKeyboardButton(text=x.month_name,
                                        callback_data=CallData(
                                            call_type=consts.MONTH_PICKED,
                                            call_val=x.month_number,
                                            opt_payload=x.year)
                                        .to_json())] for x in next_few]

    bot.send_message(chat_id=update.message.chat_id, text="На какой месяц?",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=month_keys))

    repository.update_stance(user=update.message.chat_id, stance=consts.NOTHING_PICKED)


def echo(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text=f"Введите /book для того чтобы назначить время")


def start(bot, update):
    echo(bot, update)


def start_to_end_time_pick(bot, update):
    query = update.callback_query
    username = query.message.chat_id
    bot.send_message(chat_id=username,
                     text=f"Время начала: {data_as_json(query.data).val}")

    repository.update_stance(stance=consts.START_TIME_PICKED, user=username)
    repository.update_data(user=username,
                           data=CallData(call_type=consts.START_TIME_PICKED, call_val=data_as_json(query.data).val))

    possible_start = dateutil.possible_time_for_end(username)

    time_keys = [
        [InlineKeyboardButton(text=x, callback_data=CallData(call_type=consts.END_TIME_PICKED, call_val=x).to_json())
         for x in possible_start][x:x + time_rows] for x in range(0, len(possible_start), time_rows)]

    bot.deleteMessage(chat_id=update.callback_query.message.chat_id,
                      message_id=update.callback_query.message.message_id)

    bot.send_message(chat_id=username, text="До какого времени?",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=time_keys))


def day_to_time_pick(bot, update):
    username = update.message.chat_id
    text = update.message.text
    picked_month = repository.user_data[username][consts.MONTH_PICKED]
    current_date = datetime.now()
    if dateutil.is_days_count_fits(text, repository.user_data[username][consts.MONTH_PICKED]):

        repository.update_stance(stance=consts.DAY_PICKED, user=username)
        repository.update_data(user=username, data=CallData(call_type=consts.DAY_PICKED, call_val=int(text)))

        possible_time = None

        try:
            possible_time = dateutil.possible_time_for_start(username)
        except dateutil.NoTimeAvailable:
            repository.update_stance(stance=consts.MONTH_PICKED, user=username)
            del repository.user_data[username][consts.DAY_PICKED]
            bot.send_message(chat_id=update.message.chat_id, text="На этот день свободного времени нет\nВведите другую дату или /book для того чтобы начать заново")
            return

        time_keys = [[InlineKeyboardButton(text=x, callback_data=CallData(call_type=consts.START_TIME_PICKED,
                                                                          call_val=x).to_json()) for x in
                      possible_time][x:x + time_rows] for x in range(0, len(possible_time), time_rows)]

        bot.send_message(chat_id=update.message.chat_id, text="Время начала: ",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=time_keys))
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text=f"Допустимые значения: {dateutil.available_from_to(picked_month)[0]} - {monthrange(year=current_date.year, month=int(picked_month))[1]}")


def month_to_day_pick(bot, update):
    query = update.callback_query

    bot.send_message(text=f"Выбран {dateutil.month_map[data_as_json(query.data).val]}",
                     chat_id=query.message.chat_id,
                     message_id=query.message.message_id)

    bot.send_message(text="Выберите число:",
                     chat_id=query.message.chat_id,
                     message_id=query.message.message_id)

    bot.deleteMessage(chat_id=update.callback_query.message.chat_id,
                      message_id=update.callback_query.message.message_id)

    repository.update_stance(stance=data_as_json(query.data).type,
                             user=query.message.chat_id)

    repository.update_data(user=query.message.chat_id, data=data_as_json(query.data), custom_type=consts.YEAR_PICKED)


def end_time_to_commit_pick(bot, update):
    query = update.callback_query
    username = query.message.chat_id
    user_data = repository.user_data[username]

    commit_buttons = [
        [InlineKeyboardButton(text="Да", callback_data=CallData(call_type=consts.COMMITTED, call_val="True").to_json()),
         InlineKeyboardButton(text="Нет", callback_data=CallData(call_type=consts.COMMITTED, call_val="False").to_json())]]

    bot.send_message(chat_id=username,
                     text=f"Выбрано время:\n{user_data[consts.DAY_PICKED]}"
                          f" {dateutil.morph_month_name(dateutil.month_map[user_data[consts.MONTH_PICKED]])}"
                          f" от {user_data[consts.START_TIME_PICKED]}"
                          f" до {data_as_json(query.data).val}")

    bot.send_message(chat_id=username,
                     text=f"Подтверждаете выбор?", reply_markup=InlineKeyboardMarkup(inline_keyboard=commit_buttons))

    repository.update_stance(stance=consts.END_TIME_PICKED, user=username)
    repository.update_data(user=username,
                           data=CallData(call_type=consts.END_TIME_PICKED, call_val=data_as_json(query.data).val))

    bot.deleteMessage(chat_id=update.callback_query.message.chat_id,
                      message_id=update.callback_query.message.message_id)


def commit_pick(bot, update):
    query = update.callback_query
    username = query.message.chat_id
    user_data = repository.user_data[username]

    if data_as_json(query.data).val == "True":
        repository.book_range(username)
        bot.send_message(chat_id=username, text=f"Заказ подтверждён")
        for x in adm:
            bot.send_message(chat_id=x, text=f"Заказ пользователем {query.from_user.name}\nНа дату:\n{user_data[consts.DAY_PICKED]}"
                              f" {dateutil.morph_month_name(dateutil.month_map[user_data[consts.MONTH_PICKED]])}"
                              f" от {user_data[consts.START_TIME_PICKED]}"
                              f" до {user_data[consts.END_TIME_PICKED]}")
    else:
        repository.purge_user(username)
        bot.send_message(chat_id=username, text=f"Заказ отменён")

    bot.deleteMessage(chat_id=update.callback_query.message.chat_id,
                      message_id=update.callback_query.message.message_id)


def unresolved_pick(bot, update):
    bot.deleteMessage(chat_id=update.callback_query.message.chat_id,
                      message_id=update.callback_query.message.message_id)


dispatcher_handlers = [
    CommandHandler('start', start),
    CommandHandler('book', book),
    MessageHandler(Filters.text & filters.filter_day_to_time_pick, day_to_time_pick),
    MessageHandler(Filters.text, echo),
    FilteredCallbackQueryHandler(filters=filters.filter_month_to_day_pick, callback=month_to_day_pick),
    FilteredCallbackQueryHandler(filters=filters.filter_start_to_end_time_pick, callback=start_to_end_time_pick),
    FilteredCallbackQueryHandler(filters=filters.filter_end_time_to_commit_pick, callback=end_time_to_commit_pick),
    FilteredCallbackQueryHandler(filters=filters.filter_committed, callback=commit_pick),
    CallbackQueryHandler(callback=unresolved_pick)
]

for x in dispatcher_handlers:
    dispatcher.add_handler(x)

updater.start_polling()


def error_callback(bot, update, error):
    try:
        raise error
    except (TimedOut, NetworkError):
        logging.info("Network error occurred, start polling again")
        updater.start_polling()


dispatcher.add_error_handler(error_callback)
