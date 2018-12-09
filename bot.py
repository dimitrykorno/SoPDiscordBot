import discord
from sop_analytics.main import get_menu, get_settings_str, get_defaults, parse_value, execute_report, \
    get_reports_number, get_report_name
import datetime
import os
from itertools import zip_longest

client = discord.Client()
token = 'NTE4MDUwOTcxMTc2MTQwODAx.DuaF7Q.UIYme4d7XcGQ0oLjc5VqJtNCfS4'
menu_str = get_menu()
users = {}
timeout = 60
db_users = set()
welcome_message = """
Привет! Я аналитический бот Secrets of Pandoria!
Я могу посчитать разные метрики и прислать результат.

Советы:
1) Вводи даты в формате 2018-06-14.
2) Если параметры записаны внутри [ ], то можно вводить несколько аргументов через запятую.

Если что, пиши @dimitrykorno
Пора начинать, напиши мне что-нибудь!"""


# регистрация пользователя.
# вызывается при каждом начале сессии общения
def login_user(user):
    new_user = False
    if user not in users:
        users[user] = {"in progress": False,
                       "settings": {"args": None, "defaults": None, "types": None, "changing": None, "rep num": None},
                       "result": None, "result_errors": None}
        print("User", user, "logged in. Users:", [k.name for k in users])

        # проверка на впервые пришедшего пользователя
        new_user = True
        with open("joined_users.txt", "r") as users_file:
            for u in users_file:
                if str(user) == u.strip():
                    new_user = False
                    break
        if new_user:
            with open("joined_users.txt", "a") as users_file:
                users_file.write(str(user) + "\n")

    return new_user


# обнуление измененных параметров отчета
def reset_settings(user):
    users[user]["settings"] = {"args": None, "defaults": None, "types": None, "changing": None, "rep num": None}


@client.event
async def on_ready():
    print("You are logged in. Good luck!")


@client.event
async def on_message(message):
    try:
        if message.author == client.user or message.channel not in client.private_channels or (
                        message.author in users and users[message.author]["in progress"]):
            return
        # регистрация и приветственное сообщение
        new_user = login_user(message.author)
        if new_user:
            await client.send_message(message.channel, welcome_message)
            return
        # логер
        session_log = Logger(message.author)
        users[message.author]["in progress"] = True
        await session_log.add_event("1. Start")

        # от пользователя долго нет ответа
        async def on_afk():
            await session_log.add_event("AFK " + str(timeout) + "s")
            await session_log.flush()
            await client.send_message(message.channel,
                                      "Нет ответа. Работа прекращена.\nПришли любое сообщение, чтобы начать.")
            reset_settings(message.author)
            users[message.author]["in progress"] = False

        # проверка попадания в диапазон значений отчетов
        def check_report(mes):
            correct = mes.content.isdigit() and int(mes.content) <= get_reports_number()
            return correct

        # проверка попадания в диапазон значений параметров
        def check_setting(mes):
            correct = mes.content.isdigit() and int(mes.content) <= len(
                users[mes.author]["settings"]["args"]) + 1
            return correct

        # лог
        await session_log.add_event("2. First menu print")
        # отправляем основное меню
        await client.send_message(message.channel, menu_str)
        # ЦИКЛ ВЫБОРА ОТЧЕТА
        while True:
            # ждем ввода номера отчета
            input_message = await client.wait_for_message(author=message.author, check=check_report, timeout=timeout)
            if input_message is None:
                await on_afk()
                return
            else:
                # если ответ получен, запрашиваем входные параметры для выбранной функции
                users[message.author]["settings"]["args"], \
                users[message.author]["settings"]["defaults"], \
                users[message.author]["settings"]["types"] = get_defaults(int(input_message.content))
                users[message.author]["settings"]["rep num"] = int(input_message.content)
                # отправляем меню настроек
                await client.send_message(message.channel, str(get_setting s_str(int(input_message.content))))
                # лог
                await session_log.add_event(
                    "3. Send settings " + get_report_name(users[message.author]["settings"]["rep num"]))

                # ЦИКЛ ВЫБОРА НАСТРОЕК
                while True:
                    # ждем ввода номера настройки
                    input_message = await client.wait_for_message(author=message.author, check=check_setting,
                                                                  timeout=timeout)
                    if input_message is None:
                        await on_afk()
                        return

                    # выбор НАЗАД
                    if int(input_message.content) == len(users[message.author]["settings"]["args"]):
                        await  session_log.add_event("3.3 Back in menu")
                        await client.send_message(message.channel, menu_str)
                        reset_settings(message.author)
                        break
                    # изменение параметра
                    elif int(input_message.content) < len(users[message.author]["settings"]["args"]):
                        await session_log.add_event("3.1.1 Set option " + str(
                            users[message.author]["settings"]["args"][int(input_message.content)]))

                        users[message.author]["settings"]["changing"] = int(input_message.content)
                        await client.send_message(message.channel,
                                                  "Введите новое значение " + str(
                                                      users[message.author]["settings"]["args"][
                                                          int(input_message.content)]))
                        # ожидание ввода нового значения параметра
                        input_message = await client.wait_for_message(author=message.author, timeout=timeout * 3)
                        if input_message is None:
                            await on_afk()
                            return
                        else:
                            # после ввода нового значения параметра его необходимо спарсить.
                            value_num = users[message.author]["settings"]["changing"]
                            default = users[message.author]["settings"]["defaults"][value_num]
                            def_type = users[message.author]["settings"]["types"][value_num]
                            new_value = parse_value(input_message.content, default, def_type)
                            msg = ""
                            if new_value != default:
                                users[message.author]["settings"]["defaults"][value_num] = new_value
                            else:
                                msg += "Нет изменений в " + str(
                                    users[message.author]["settings"]["args"][value_num]) + ".\n"
                            msg += str(get_settings_str(users[message.author]["settings"]["rep num"],
                                                        [users[message.author]["settings"]["args"],
                                                         users[message.author]["settings"]["defaults"],
                                                         users[message.author]["settings"]["types"]]))
                            await client.send_message(message.channel, msg)
                            await session_log.add_event("3.1.2 Option set " + str(new_value))

                    # запуск отчета
                    elif int(input_message.content) == len(users[message.author]["settings"]["args"]) + 1:
                        await session_log.add_event(
                            "3.2.1 Run report " + get_report_name(users[message.author]["settings"]["rep num"]))
                        if len(db_users) == 0:
                            await client.send_message(message.channel,
                                                      "Ожидайте результатов. Это может занять некоторое время.")
                        else:
                            await client.send_message(message.channel,
                                                      "База данных занята. Вы " + str(
                                                          len(db_users) + 1) + "й в очереди. Ожидайте результатов.")
                        db_users.add(message.author)
                        users[message.author]["results"] = None

                        # ставим выполнение отчета в отдельный поток
                        try:
                            await client.send_typing(message.channel)
                            users[message.author]["result"] = await client.loop.run_in_executor(None, report_task,
                                                                                                message.author,
                                                                                                users[message.author][
                                                                                                    "settings"][
                                                                                                    "rep num"],
                                                                                                users[message.author][
                                                                                                    "settings"][
                                                                                                    "defaults"])

                        except Exception as ex:
                            print("Error during report", ex.args)
                            await session_log.add_event("Error during report " + str(ex.args))
                            await client.send_message(message.channel,
                                                      "Произошла ошибка, проверьте правильность введенных параметров,\n"
                                                      "попробуйте позже или обратитесь к администратору")
                            db_users.discard(message.author)
                            users[message.author]["in progress"] = False
                            return
                        finally:
                            if users[message.author]["result"].errors:
                                await client.send_message(message.channel, users[message.author]["result"].errors)
                        db_users.discard(message.author)
                        await session_log.add_event(
                            "3.2.2 Report executed " + get_report_name(users[message.author]["settings"]["rep num"]))

                        files = users[message.author]["result"].value
                        if files is None or files == []:
                            await client.send_message(message.channel, "Нет результатов, либо произошла ошибка.")
                        else:
                            await client.send_message(message.channel, "Ваш отчёт готов!")
                            await try_send_files(files, message.channel)
                        await session_log.add_event(
                            "3.2.3 Result sent " + get_report_name(users[message.author]["settings"]["rep num"]))
                        reset_settings(message.author)
                        users[message.author]["in progress"] = False
                        await session_log.flush()
                        return
    except Exception as ex:
        print("Something went wrong " + str(ex.args))
        if users[message.author]["result_errors"]:
            await client.send_message(message.channel, users[message.author]["result"].errors)
        users[message.author]["in progress"] = False
        reset_settings(message.author)
        db_users.discard(message.author)


async def correct_filesize(file):
    return os.path.getsize(file) < 8000 * 1000


def split_txt(file, n):
    def grouper(n, iterable, fillvalue=None):
        "Collect data into fixed-length chunks or blocks"
        # grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx
        args = [iter(iterable)] * n
        return zip_longest(fillvalue=fillvalue, *args)

    filename = file[:-4]
    result_files = []
    with open(file, "r") as f:
        for i, g in enumerate(grouper(n, f, fillvalue=''), 1):
            new_filename = filename + "_" + str(i * n) + ".txt"
            with open(new_filename, "w") as fout:
                fout.writelines(g)
                result_files.append(new_filename)
    return result_files


async def try_send_files(files, channel):
    # макс длина txt
    n = 100000
    for file in files:
        if not await correct_filesize(file):
            if file[-4:] != ".txt":
                await client.send_message(channel, "Слишком большой файл. Попробуйте уменьшить сегмент.")
                return
            else:
                await client.send_message(channel, "Слишком большой файл. Попытка разбить на части.")
                files += await client.loop.run_in_executor(None, split_txt, file, n)
                n *= 0.9 * n
                continue
        try:
            await client.send_file(channel, file)
            print("send", file, "to", channel)
        except Exception as ex:
            print("Error sending file", ex.args)


class CallableResult(object):
    errors = None
    value = None

    def __init__(self, value):
        # print(value)
        self.errors = value[0]
        self.value = value[1]

    def __call__(self):
        return self


def report_task(user, rep_num, params):
    return CallableResult(execute_report(user, rep_num, params))


class Logger:
    author = ""
    session_string = ""

    def __init__(self, author):
        self.author = str(author)

    async def add_event(self, value):
        self.session_string += str(self.author) + ": " + str(datetime.datetime.now()) + " " + value + "\n"

    async def flush(self):
        with open(self.author + ".txt", "a") as log_file:
            log_file.write(self.session_string + "\/-------------------------\/-------------------------\/\n")


client.run(token)
