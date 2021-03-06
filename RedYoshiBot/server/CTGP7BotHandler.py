from .CTGP7ServerHandler import CTGP7ServerHandler
from .CTGP7ServerDatabase import ConsoleMessageType
from ..RedYoshiBot import ch_list, is_channel, is_channel_private, get_role, parsetime, sendMultiMessage, escapeFormatting, MODERATORROLE_ID, ADMINROLE_ID
from ..CTGP7Defines import CTGP7Defines
import discord
import asyncio
import threading
import traceback
import datetime
import profanity_check
import matplotlib.pyplot as plt
import io

SELF_BOT_MEMBER = None
SELF_BOT_SERVER = None

def handler_server_update_globals(bot_member, bot_server):
    global SELF_BOT_MEMBER
    global SELF_BOT_SERVER
    SELF_BOT_MEMBER = bot_member
    SELF_BOT_SERVER = bot_server

def server_help_array():
    return {
        "help": ">@RedYoshiBot server help\nGets the help for the server specific commands.",
        "stats": ">@RedYoshiBot server stats (ct/ot/ba)\nGets the usage stats for custom tracks (ct), original tracks (ot) or battle arenas (ba)."
    }
def staff_server_help_array():
    return {
        "version": ">@RedYoshiBot server version (ctww/beta) (newvalue)\nSets the ctww or beta values. If \'newvalue\' is not specified, the current version is displayed.",
        "kick": ">@RedYoshiBot server kick (consoleID) (time) (message)\nKicks the console (hex format, 0 for everyone) for the specified time (for example: 2h, 12m, 7d, etc, or 0m for a single time) with the specified message. Takes effect after the next race.",
        "skick": ">@RedYoshiBot server skick (consoleID) (time) (message)\nSilently kicks the console (hex format, 0 for everyone) for the specified time (for example: 2h, 12m, 7d, etc, or 0m for a single time) with the specified message. Takes effect after the next race.",
        "ban": ">@RedYoshiBot server ban (consoleID) (message)\nPermanently bans the console (hex format, 0 for everyone) with the specified message (Use kick for temporary bans). Takes effect after the next race.",
        "sban": ">@RedYoshiBot server sban (consoleID) (message)\nPermanently silently bans the console (hex format, 0 for everyone) with the specified message (Use kick for temporary bans). Takes effect after the next race.",
        "message": ">@RedYoshiBot server message (consoleID) (time) (message)\nShows a message to the console (hex format, 0 for everyone) upon login for the specified time (for example: 2h, 12m, 7d, etc, or 0m for a single time).",
        "clear": ">@RedYoshiBot server clear (consoleID)\nClears all the messages/kicks/bans associated with the console (hex format, 0 for everyone).",
        "disband": ">@RedYoshiBot server disband (roomID)\nDisbands the specified room ID, kicking all players.",
        "console_verify": ">@RedYoshiBot server console_verify (get/set/clear) (consoleID)\nSets or clears the verification mark for the specified console.",
        "console_admin": ">@RedYoshiBot server console_admin (get/set/clear) (consoleID)\nSets or clears the admin status for the specified console.",
        "region": ">@RedYoshiBot server region (newvalue)\nSets the CTWW/CD online region in the server.",
        "manage_vr": ">@RedYoshiBot server manage_vr (get/set) (consoleID) (ctww/cd) (newvalue)\nGets or sets the VR for the specified console (Don't set if console is in racing state online)."
    }
    
def staff_server_command_level():
    return {
        "version": 0,
        "help": 1,
        "kick": 1,
        "skick": 1,
        "ban": 1,
        "sban": 1,
        "message": 1,
        "clear": 1,
        "disband" : 1,
        "stats": 1,
        "console_verify": 1,
        "console_admin": 0,
        "region": 0,
        "manage_vr": 1
    }

async def staff_server_can_execute(message, command, silent=False):
    retVal = False
    if (is_channel(message, ch_list()["STAFF"])):
        moderatorRole = get_role(MODERATORROLE_ID())
        adminRole = get_role(ADMINROLE_ID())
        hasMod = moderatorRole in message.author.roles
        hasAdmin = (adminRole in message.author.roles) or message.author.id == SELF_BOT_SERVER.owner.id
        privilegeLevel = 0 if hasAdmin else (1 if hasMod else 2)
        try:
            retVal = staff_server_command_level()[command] >= privilegeLevel
        except:
            retVal = False
    if (not retVal and not silent):
        await message.channel.send("{}, you don't have permission to do that!".format(message.author.name))
    return retVal

def get_server_bot_args(content: str, maxslplits=-1): # splits: amount of cuts after "server"
    realsplits = maxslplits + 1 if maxslplits != -1 else maxslplits
    return content.split(maxsplit=realsplits)[1:]

def gen_course_usage_embed(ctgp7_server: CTGP7ServerHandler, course_type: int):
    mostTracks = ctgp7_server.database.get_most_played_tracks(course_type, 10000)
    tName = ""
    if (course_type == 0):
        tName = "Original Tracks"
    elif (course_type == 1):
        tName = "Custom Tracks"
    elif (course_type == 2):
        tName = "Battle Arenas"
    embed = discord.Embed(title="Most Played Tracks", description=tName, color=0xff0000, timestamp=datetime.datetime.utcnow())
    currTrack = 1
    for d in range(0, 4):
        slic = []
        if (d < 2):
            slic = mostTracks[:(len(mostTracks)//2)]
        else:
            slic = mostTracks[(len(mostTracks)//2):]
        if (d == 2):
            embed.add_field(name="** **", value="** **", inline=False)
        mostPlayedStr = "```\n"
        for k in slic:
            if (d % 2 == 0):
                trackName = CTGP7Defines.getTrackNameFromSzs(k[0])
                position = str(currTrack)
                positionSpaces = " " * max((4 - len(position)), 0)
                mostPlayedStr += "{}.{}{}\n".format(position, positionSpaces, trackName)
                currTrack += 1
            else:
                mostPlayedStr += "{}\n".format(str(k[1]))
        mostPlayedStr += "```"
        embed.add_field(name="** **", value=mostPlayedStr, inline=True)
    return embed

server_message_logger_lock = threading.Lock()
server_message_logger_pending = ""
def server_message_logger_callback(text: str):
    global server_message_logger_lock
    global server_message_logger_pending
    with server_message_logger_lock:
        server_message_logger_pending += text

async def server_message_logger(ctgp7_server: CTGP7ServerHandler):
    global server_message_logger_lock
    global server_message_logger_pending
    with kick_message_logger_lock:
        if (len(server_message_logger_pending) > 1800): # Reduces the amount of messages sent to discord api
            chPrivate = SELF_BOT_SERVER.get_channel(ch_list()["ONLINELOGS"])
            await sendMultiMessage(chPrivate, escapeFormatting(server_message_logger_pending, True), "```\n", "```")
            server_message_logger_pending = ""

kick_message_logger_lock = threading.Lock()
kick_message_logger_pending = []
def kick_message_callback(cID, messageType, message, amountMin, isSilent):
    global kick_message_logger_lock
    global kick_message_logger_pending
    with kick_message_logger_lock:
        kick_message_logger_pending.append([cID, messageType, message, amountMin, isSilent])

async def kick_message_logger(ctgp7_server: CTGP7ServerHandler):
    global kick_message_logger_lock
    global kick_message_logger_pending
    with kick_message_logger_lock:
        for m in kick_message_logger_pending:
            cID = m[0]
            messageType = m[1]
            message = m[2]
            amountMin = m[3]
            isSilent = m[4]
            if (isSilent or (messageType != ConsoleMessageType.SINGLE_KICKMESSAGE.value and messageType != ConsoleMessageType.TIMED_KICKMESSAGE.value) or cID == 0):
                continue
            publicCID = "0x\\*\\*\\*\\*\\*\\*\\*\\*\\*\\*\\*\\*\\*\\*{:04X}".format(cID & 0xFFFF)
            embedPublic=discord.Embed(title="Kick Report", description="Console ID: {}".format(publicCID), color=0xff0000, timestamp=datetime.datetime.utcnow())
            embedPrivate=discord.Embed(title="Kick Report", description="Console ID: 0x{:016X}".format(cID), color=0xff0000, timestamp=datetime.datetime.utcnow())
            embedPublic.add_field(name="Reason", value=message, inline=False)
            embedPrivate.add_field(name="Reason", value=message, inline=False)
            if (messageType == ConsoleMessageType.TIMED_KICKMESSAGE.value):
                time = ""
                if amountMin is None:
                    time = "Permanent"
                else:
                    days = int(amountMin // (60 * 24))
                    hours = int((amountMin // 60) % 24)
                    minutes = int((amountMin) % 60)
                    time = "{} days,  {} hours, {} minutes".format(days, hours, minutes)
                embedPublic.add_field(name="Duration", value=time, inline=False)
                embedPrivate.add_field(name="Duration", value=time, inline=False)
            chPublic = SELF_BOT_SERVER.get_channel(ch_list()["KICKS"])
            chPrivate = SELF_BOT_SERVER.get_channel(ch_list()["STAFFKICKS"])
            await chPublic.send(embed=embedPublic)
            await chPrivate.send(embed=embedPrivate)
        kick_message_logger_pending = []
            

tried_edit_stats_message_times = 0
stats_curr_online_users = 0
stats_curr_online_rooms = 0
stats_curr_online_stuff_changed = True
stats_message_id = 0
vr_message_id = 0
graph_launches_message_id = 0
last_graph_update_date = None

async def update_graph_message(ctgp7_server: CTGP7ServerHandler):
    global graph_launches_message_id
    global last_graph_update_date
    DAYS_PAST = 30
    today = datetime.datetime.utcnow().date()
    if (today == last_graph_update_date):
        return
    last_graph_update_date = today
    x = []
    y1 = []
    y2 = []
    for i in range(DAYS_PAST):
        date = today - datetime.timedelta(days=DAYS_PAST - i)
        x.append(date.strftime("%b %-d"))
        y1.append(ctgp7_server.database.get_daily_launches(date))
        y2.append(ctgp7_server.database.get_daily_unique_consoles(date))
    
    plt.rcParams["figure.figsize"] = (plt.rcParamsDefault["figure.figsize"][0] * 1.75, plt.rcParamsDefault["figure.figsize"][1])
    plt.plot(x, y1, color = "dodgerblue", label = "Launches", marker="o", markersize=3)
    plt.plot(x, y2, color = "lightskyblue", linestyle='dashed', label = "New Consoles", marker="o", markersize=3)
    for i,j in zip(x,y1):
        plt.annotate(str(j),xy=(i,j), fontsize=8)
    for i,j in zip(x,y2):
        plt.annotate(str(j),xy=(i,j), fontsize=8)
    plt.xticks(rotation = 45)
    plt.subplots_adjust(bottom=0.15)
    plt.grid()
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.clf()
    plt.rcParams["figure.figsize"] = plt.rcParamsDefault["figure.figsize"]
    buf.seek(0)

    file = discord.File(fp=buf, filename="image.png")
    embed = discord.Embed(title="Daily Statistics (UTC)", color=0xff0000)
    chPrivate = SELF_BOT_SERVER.get_channel(ch_list()["ONLINELOGS"])
    tmpMsg = await chPrivate.send(file=file)
    imageUrl = tmpMsg.attachments[0].url
    embed.set_image(url=imageUrl)
    ch = SELF_BOT_SERVER.get_channel(ch_list()["STATS"])
    msg = await ch.fetch_message(graph_launches_message_id)
    await msg.edit(embed=embed, content=None)
    buf.close()

async def update_stats_message(ctgp7_server: CTGP7ServerHandler):
    global tried_edit_stats_message_times
    global stats_curr_online_stuff_changed
    global stats_curr_online_users
    global stats_curr_online_rooms
    global stats_message_id
    global vr_message_id
    stats_curr_online_stuff_changed = False
    try:
        ch = SELF_BOT_SERVER.get_channel(ch_list()["STATS"])
        if (ch is None):
            raise Exception()
        msg = await ch.fetch_message(stats_message_id)
        vrLead = await ch.fetch_message(vr_message_id)
        if (msg is None or msg.author != SELF_BOT_MEMBER or vrLead is None or vrLead.author != SELF_BOT_MEMBER):
            raise Exception()
        tried_edit_stats_message_times = 0

        genStats = ctgp7_server.database.get_stats()
        totOfflineRaces = genStats["races"] + genStats["ttrials"] + genStats["coin_battles"] + genStats["balloon_battles"]
        totOnlineRaces = genStats["online_races"] + genStats["comm_races"] + genStats["ctww_races"] + genStats["cd_races"] + genStats["online_coin_battles"] + genStats["online_balloon_battles"]
        mostTracks = ctgp7_server.database.get_most_played_tracks(1, 10)
        uniqueConsoles = ctgp7_server.database.get_unique_console_count()
        uniqueOnlineUsers = ctgp7_server.database.get_unique_console_vr_count()

        embed=discord.Embed(title="CTGP-7 Statistics", description="Statistics from all CTGP-7 players!", color=0xff0000, timestamp=datetime.datetime.utcnow())
        embed.set_thumbnail(url=str(SELF_BOT_SERVER.icon_url))
        embed.add_field(name="Total Launches", value=str(genStats["launches"]), inline=True)
        embed.add_field(name="Unique Consoles", value=str(uniqueConsoles), inline=True)
        embed.add_field(name="** **", value="** **", inline=False)
        embed.add_field(name="Total Offline Races", value=str(totOfflineRaces), inline=False)
        embed.add_field(name="Normal Races", value=str(genStats["races"]), inline=True)
        embed.add_field(name="Time Trials", value=str(genStats["ttrials"]), inline=True)
        embed.add_field(name="Coin Battles", value=str(genStats["coin_battles"]), inline=True)
        embed.add_field(name="Balloon Battles", value=str(genStats["balloon_battles"]), inline=True)
        embed.add_field(name="** **", value="** **", inline=False)
        embed.add_field(name="Total Online Races", value=str(totOnlineRaces), inline=False)
        embed.add_field(name="Vanilla Races", value=str(genStats["online_races"]), inline=True)
        embed.add_field(name="Community Races", value=str(genStats["comm_races"]), inline=True)
        embed.add_field(name="CTWW Races", value=str(genStats["ctww_races"]), inline=True)
        embed.add_field(name="Countdown Races", value=str(genStats["cd_races"]), inline=True)
        embed.add_field(name="Coin Battles", value=str(genStats["online_coin_battles"]), inline=True)
        embed.add_field(name="Balloon Battles", value=str(genStats["online_balloon_battles"]), inline=True)
        embed.add_field(name="** **", value="** **", inline=False)
        embed.add_field(name="Total Logins", value=str(genStats["total_logins"]), inline=True)
        embed.add_field(name="Unique Logins", value=str(uniqueOnlineUsers), inline=True)
        embed.add_field(name="Total Online Rooms", value=str(genStats["total_rooms"]), inline=True)
        embed.add_field(name="Current Users Online", value=str(stats_curr_online_users), inline=True)
        embed.add_field(name="Current Rooms Online", value=str(stats_curr_online_rooms), inline=True)
        embed.add_field(name="** **", value="** **", inline=False)
        mostPlayedStr = "```\n"
        currTrack = 1
        for k in mostTracks:
            trackName = CTGP7Defines.getTrackNameFromSzs(k[0])
            trackNameSpaces = " " * max((24 - len(trackName)), 0)
            position = str(currTrack)
            positionSpaces = " " * max((4 - len(position)), 0)
            mostPlayedStr += "{}.{}{}{}{}\n".format(position, positionSpaces, trackName, trackNameSpaces, str(k[1]))
            currTrack += 1
        mostPlayedStr += "```"
        embed.add_field(name="Most Played Tracks", value=mostPlayedStr, inline=False)
        await msg.edit(embed=embed, content=None)
        tried_edit_stats_message_times = 0

        vrRankCtww = ctgp7_server.database.get_most_users_vr(0, 20)
        vrRankCD = ctgp7_server.database.get_most_users_vr(1, 20)
        embed=discord.Embed(title="CTWW Leaderboard", description="Players with most VR!", color=0xff0000, timestamp=datetime.datetime.utcnow())
        currPos = 1
        for i in range(2):
            leaderText = "```"
            leaderTextVR = "```"
            for user in (vrRankCtww if i == 0 else vrRankCD):
                userName = ctgp7_server.database.get_console_last_name(user[0])
                position = str(currPos)
                positionSpaces = " " * max((4 - len(position)), 0)
                leaderText += "{}.{}{}{}\n".format(position, positionSpaces, userName.replace("\u2705", ""), " \u2705" if ctgp7_server.database.get_console_is_verified(user[0]) else "")
                leaderTextVR += "{}.{}{}vr\n".format(position, positionSpaces, str(user[1]))
                currPos += 1
            leaderText += "```"
            leaderTextVR += "```"
            embed.add_field(name="CTWW" if i == 0 else "Countdown", value=leaderText, inline=True)
            embed.add_field(name="** **", value=leaderTextVR, inline=True)
            currPos = 1
            if (i == 0):
                embed.add_field(name="** **", value="** **", inline=False)
        await vrLead.edit(embed=embed, content=None)
        
        await update_graph_message(ctgp7_server)

    except Exception:
        tried_edit_stats_message_times += 1
        if (tried_edit_stats_message_times == 6 * 30):
            staff_chan = SELF_BOT_SERVER.get_channel(ch_list()["STAFF"])
            await staff_chan.send("<@&383673430030942208> Failed to update stats for more than 30 min.")
        if (CTGP7ServerHandler.debug_mode):
            traceback.print_exc()
        return

async def prepare_server_channels(ctgp7_server: CTGP7ServerHandler):
    global stats_message_id
    global vr_message_id
    global graph_launches_message_id
    ctwwChan = SELF_BOT_SERVER.get_channel(ch_list()["CTWW"])
    async for m in ctwwChan.history(limit=200):
        await m.delete()
    statsChan = SELF_BOT_SERVER.get_channel(ch_list()["STATS"])
    mIds = []
    i = 0
    async for m in statsChan.history(limit=200, oldest_first=True):
        if (i < 3 and m.author.id == SELF_BOT_MEMBER.id):
            mIds.append(m.id)
            i += 1
        else:
            await m.delete()
    stats_message_id = mIds[0] if len(mIds) > 0 else (await statsChan.send("Loading...")).id
    graph_launches_message_id = mIds[1] if len(mIds) > 1 else (await statsChan.send("Loading...")).id
    vr_message_id = mIds[2] if len(mIds) > 2 else (await statsChan.send("Loading...")).id

all_prev_room_msg_ids = set()
async def update_online_room_info(ctgp7_server: CTGP7ServerHandler):
    global all_prev_room_msg_ids
    global stats_curr_online_stuff_changed
    global stats_curr_online_users
    global stats_curr_online_rooms
    ctwwChan = SELF_BOT_SERVER.get_channel(ch_list()["CTWW"])
    ctgp7_server.ctwwHandler.purge_users(datetime.timedelta(minutes=10))
    ctgp7_server.ctwwHandler.purge_rooms()
    serverInfo = ctgp7_server.ctwwHandler.fetch_state()
    currUser = serverInfo["userCount"]
    if (stats_curr_online_users != currUser):
        stats_curr_online_users = currUser
        stats_curr_online_stuff_changed = True
    currRoom = serverInfo["roomCount"]
    if (stats_curr_online_rooms != currRoom):
        stats_curr_online_rooms = currRoom
        stats_curr_online_stuff_changed = True
    nowUser = serverInfo["newUserCount"]
    ctgp7_server.database.increment_general_stats("total_logins", nowUser)
    nowRoom = serverInfo["newRoomCount"]
    ctgp7_server.database.increment_general_stats("total_rooms", nowRoom)
    if (nowUser != 0 or nowRoom != 0):
        ctgp7_server.database.set_stats_dirty(True)
    currMsgIds = set()
    for room in serverInfo["rooms"]:
        msgID = room["messageID"]
        msg = None
        if (room["updated"]):
            try:
                if (msgID != 0):
                    msg = await ctwwChan.fetch_message(msgID)
            except:
                msgID = 0
            if msgID == 0:
                msg = await ctwwChan.send("Room is being created...")
                msgID = msg.id
                ctgp7_server.ctwwHandler.update_room_messageID(room["gID"], msgID)
            embed=discord.Embed(title="{} Room".format(room["gameMode"]), description="State: {}\nID: 0x{:08X}".format(room["state"], room["fakeID"]), color=0xff0000, timestamp=datetime.datetime.utcnow())
            playerString = "```\n"
            for player in room["players"]:
                vrStr = ""
                if (player["vrIncr"] is not None):
                    vrStr = "{}({:+}) VR".format(player["vr"], player["vrIncr"])
                else:
                    vrStr = "{} VR".format(player["vr"])
                playerString += "{}{} - {} - {}\n".format(player["name"].replace("\u2705", ""), " \u2705" if player["verified"] else "", vrStr, player["state"])
            playerString += "```"
            if (playerString == "```\n```"):
                playerString = "```\n- (None)\n```"
            embed.add_field(name="Players", value=playerString, inline=False)
            await msg.edit(embed=embed, content=None)
            profanityProb = profanity_check.predict_prob([playerString])[0]
            if (False): # Disable this for now until I find a proper way to handle it
                chPrivate = SELF_BOT_SERVER.get_channel(ch_list()["STAFFKICKS"])
                embed1 = discord.Embed(title="Possible profanity.", description="Probability: {:02f}%".format(profanityProb * 100), color=0xff7f00, timestamp=datetime.datetime.utcnow())
                embed1.add_field(name="Players", value=playerString)
                playerString = "```\n"
                for player in room["players"]:
                    playerString += "- 0x{:016X} ({})\n".format(player["cID"], player["miiName"])
                playerString += "```"
                if (playerString == "```\n```"):
                    playerString = "```\n- (None)\n```"
                embed1.add_field(name="Players IDs", value=playerString, inline=False)
                await chPrivate.send(embed=embed1)
            if (room["log"]):
                playerString = "```\n"
                for player in room["players"]:
                    playerString += "- 0x{:016X} ({})\n".format(player["cID"], player["miiName"])
                playerString += "```"
                if (playerString == "```\n```"):
                    playerString = "```\n- (None)\n```"
                embed.add_field(name="Room ID", value="0x{:08X}".format(room["gID"]))
                embed.add_field(name="Players IDs", value=playerString, inline=False)
                chPrivate = SELF_BOT_SERVER.get_channel(ch_list()["ONLINELOGS"])
                await chPrivate.send(embed=embed)
            
        currMsgIds.add(msgID)
    otherRooms = all_prev_room_msg_ids - currMsgIds
    for mID in otherRooms:
        try:
           msg = await ctwwChan.fetch_message(mID)
           await msg.delete()
        except:
            pass
    all_prev_room_msg_ids = currMsgIds
    pass
server_bot_loop_dbcommit_cnt = 0
async def server_bot_loop(ctgp7_server: CTGP7ServerHandler):
    firstLoop = True
    global stats_curr_online_stuff_changed
    global server_bot_loop_dbcommit_cnt
    while (True):
        try:
            if (firstLoop):
                await prepare_server_channels(ctgp7_server)
            await update_online_room_info(ctgp7_server)
            if (firstLoop or ctgp7_server.database.get_stats_dirty() or stats_curr_online_stuff_changed):
                await update_stats_message(ctgp7_server)
                ctgp7_server.database.set_stats_dirty(False)
            await kick_message_logger(ctgp7_server)
            await server_message_logger(ctgp7_server)
            server_bot_loop_dbcommit_cnt += 1
            if (server_bot_loop_dbcommit_cnt >= 60 * 5 / 5): # Commit every 5 minutes
                ctgp7_server.database.commit()
                server_bot_loop_dbcommit_cnt = 0
            firstLoop = False
        except:
            traceback.print_exc()
            pass
        await asyncio.sleep(5)
stats_command_last_exec = datetime.datetime.utcnow()
async def handle_server_command(ctgp7_server: CTGP7ServerHandler, message: discord.Message):
    global stats_command_last_exec
    try:
        bot_cmd = get_server_bot_args(message.content, 2)[1]
    except IndexError:
        await message.reply( "Invalid syntax, use `@RedYoshiBot server help` to get all the available server commands")
        return
    if (bot_cmd == "help"):
        tag = get_server_bot_args(message.content)
        if is_channel(message, ch_list()["BOTCHAT"]) or await staff_server_can_execute(message, bot_cmd, silent=True) or is_channel_private(message.channel):
            if (len(tag) > 2):
                if await staff_server_can_execute(message, bot_cmd, silent=True):
                    if tag[2] in staff_server_help_array():
                        await message.reply( "Here is the help for the specified server command:\r\n```" + staff_server_help_array()[tag[2]] + "```")
                        return
                if tag[2] in server_help_array():
                    await message.reply( "Here is the help for the specified server command:\r\n```" + server_help_array()[tag[2]] + "```")
                else:
                    await message.reply( "Unknown server command, use `@RedYoshiBot server help` to get a list of all the available server commands.")
            else:
                help_str = "Here is a list of all the available server commands:\n\n"
                for index, _ in server_help_array().items():
                    help_str += "`" + index + "`, "
                help_str = help_str[:-2]
                help_str += "\n\nUse `@RedYoshiBot server help (command)` to get help of a specific server command."
                await message.reply( help_str)
                if await staff_server_can_execute(message, bot_cmd, silent=True):
                    help_str = "\nHere is a list of all the available staff server commands:\n\n"
                    for index, _ in staff_server_help_array().items():
                        help_str += "`" + index + "`, "
                    help_str = help_str[:-2]
                    help_str += "\n\nUse `@RedYoshiBot server help (command)` to get help of a specific server command."
                    await message.reply( help_str)
        else:
            await message.reply( "`@RedYoshiBot server help` can only be used in <#324672297812099093> or DM.")
            return
    elif bot_cmd == "version":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content)
            if (len(tag) != 3 and len(tag) != 4):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()["version"] + "```")
                return
            mode = tag[2]
            if mode not in ["ctww", "beta"]:
                await message.reply( "Invalid option `{}`, correct usage:\r\n```".format( mode) + staff_server_help_array()["version"] + "```")
                return
            if (len(tag) == 3):
                version = -1
                if mode == "ctww":
                    version = ctgp7_server.database.get_ctww_version()
                elif mode == "beta":
                    version = ctgp7_server.database.get_beta_version()
                await message.reply( "Current {} version is: {}".format( mode, version))
                return
            else:
                try:
                    version = int(tag[3])
                except ValueError:
                    await message.reply( "Invalid number.")
                    return
                if mode == "ctww":
                    ctgp7_server.database.set_ctww_version(version)
                elif mode == "beta":
                    ctgp7_server.database.set_beta_version(version)
                await message.reply( "{} version set to: {}".format( mode, version))
                return
    elif bot_cmd == "region":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content)
            if (len(tag) != 2 and len(tag) != 3):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()["region"] + "```")
                return
            if (len(tag) == 2):
                region = -1
                region = ctgp7_server.database.get_online_region()
                await message.reply( "Current region is: {}".format(region))
                return
            else:
                try:
                    region = int(tag[2])
                except ValueError:
                    await message.reply( "Invalid number.")
                    return
                ctgp7_server.database.set_online_region(region)
                await message.reply( "Region set to: {}".format(region))
                return
    elif bot_cmd == "kick" or bot_cmd == "skick":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content, 4)
            if (len(tag) != 5):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()[bot_cmd] + "```")
                return
            consoleID = tag[2]
            if (consoleID.startswith("0x")):
                consoleID = consoleID[2:]
            try:
                consoleID = int(consoleID, 16)
            except ValueError:
                await message.reply( "Invalid console ID.")
                return
            if (consoleID == 0):
                await message.reply( "**WARNING THIS OPERATION AFFECTS ALL CONSOLES.**")
            kickTime = parsetime(tag[3])
            if kickTime[0] == -1:
                await message.reply( "Invalid time specified.")
                return
            messageType = ConsoleMessageType.TIMED_KICKMESSAGE.value
            if (kickTime[0] == 0):
                messageType = ConsoleMessageType.SINGLE_KICKMESSAGE.value
            ctgp7_server.database.set_console_message(consoleID, messageType, tag[4], None if kickTime[0] == 0 else kickTime[0], bot_cmd == "skick")
            await message.reply( "Operation succeeded.")
            return
    elif bot_cmd == "ban" or bot_cmd == "sban":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content, 3)
            if (len(tag) != 4):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()[bot_cmd] + "```")
                return
            consoleID = tag[2]
            if (consoleID.startswith("0x")):
                consoleID = consoleID[2:]
            try:
                consoleID = int(consoleID, 16)
            except ValueError:
                await message.reply( "Invalid console ID.")
                return
            if (consoleID == 0):
                await message.reply( "**WARNING THIS OPERATION AFFECTS ALL CONSOLES.**")
            messageType = ConsoleMessageType.TIMED_KICKMESSAGE.value
            ctgp7_server.database.set_console_message(consoleID, messageType, tag[3], None, bot_cmd == "sban")
            await message.reply( "Operation succeeded.")
            return
    elif bot_cmd == "message":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content, 4)
            if (len(tag) != 5):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()["message"] + "```")
                return
            consoleID = tag[2]
            if (consoleID.startswith("0x")):
                consoleID = consoleID[2:]
            try:
                consoleID = int(consoleID, 16)
            except ValueError:
                await message.reply( "Invalid console ID.")
                return
            if (consoleID == 0):
                await message.reply( "**WARNING THIS OPERATION AFFECTS ALL CONSOLES.**")
            msgTime = parsetime(tag[3])
            if msgTime[0] == -1:
                await message.reply( "Invalid time specified.")
                return
            messageType = ConsoleMessageType.TIMED_MESSAGE.value
            messageTime = msgTime[0]
            if (msgTime[0] == 0):
                messageType = ConsoleMessageType.SINGLE_MESSAGE.value
                messageTime = None
            elif (msgTime[0] >= parsetime("10y")[0]): # Permanent message
                messageTime = None
            ctgp7_server.database.set_console_message(consoleID, messageType, tag[4], messageTime)
            await message.reply( "Operation succeeded.")
            return
    elif bot_cmd == "clear":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content, 2)
            if (len(tag) != 3):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()["clear"] + "```")
                return
            consoleID = tag[2]
            if (consoleID.startswith("0x")):
                consoleID = consoleID[2:]
            try:
                consoleID = int(consoleID, 16)
            except ValueError:
                await message.reply( "Invalid console ID.")
                return
            if (consoleID == 0):
                await message.reply( "**WARNING THIS OPERATION AFFECTS ALL CONSOLES.**")
            
            ctgp7_server.database.delete_console_message(consoleID)
            await message.reply( "Operation succeeded.")
            return
    elif bot_cmd == "disband":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content, 2)
            if (len(tag) != 3):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()["disband"] + "```")
                return
            roomID = tag[2]
            if (roomID.startswith("0x")):
                roomID = roomID[2:]
            try:
                roomID = int(roomID, 16)
            except ValueError:
                await message.reply( "Invalid room ID.")
                return
            if (ctgp7_server.ctwwHandler.disband_room(roomID)):
                await message.reply( "Operation succeeded.")
            else:
                await message.reply( "The specified room is not active.")
            return
    elif bot_cmd == "console_verify":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content, 3)
            if (len(tag) != 4):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()[bot_cmd] + "```")
                return
            mode = tag[2]
            consoleID = tag[3]
            if (consoleID.startswith("0x")):
                consoleID = consoleID[2:]
            try:
                consoleID = int(consoleID, 16)
                if (consoleID == 0):
                    raise ValueError()
            except ValueError:
                await message.reply( "Invalid console ID.")
                return
            if mode not in ["get", "set", "clear"]:
                await message.reply( "Invalid option `{}`, correct usage:\r\n```".format( mode) + staff_server_help_array()[bot_cmd] + "```")
                return
            if (mode == "get"):
                if (ctgp7_server.database.get_console_is_verified(consoleID)):
                    await message.reply("The specified console ID is verified.")
                else:
                    await message.reply("The specified console ID is not verified.")
            else:
                ctgp7_server.database.set_console_is_verified(consoleID, mode == "set")
                await message.reply( "Operation succeeded.")
    elif bot_cmd == "console_admin":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content, 3)
            if (len(tag) != 4):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()[bot_cmd] + "```")
                return
            mode = tag[2]
            consoleID = tag[3]
            if (consoleID.startswith("0x")):
                consoleID = consoleID[2:]
            try:
                consoleID = int(consoleID, 16)
                if (consoleID == 0):
                    raise ValueError()
            except ValueError:
                await message.reply( "Invalid console ID.")
                return
            if mode not in ["get", "set", "clear"]:
                await message.reply( "Invalid option `{}`, correct usage:\r\n```".format( mode) + staff_server_help_array()[bot_cmd] + "```")
                return
            if (mode == "get"):
                if (ctgp7_server.database.get_console_is_admin(consoleID)):
                    await message.reply("The specified console ID is admin.")
                else:
                    await message.reply("The specified console ID is not admin.")
            else:
                ctgp7_server.database.set_console_is_admin(consoleID, mode == "set")
                await message.reply( "Operation succeeded.")
    elif bot_cmd == "stats":
        tag = get_server_bot_args(message.content)
        if (len(tag) != 3):
            await message.reply( "Invalid syntax, correct usage:\r\n```" + server_help_array()["stats"] + "```")
            return
        if (tag[2] not in ["ct", "ot", "ba"]):
            await message.reply( "Invalid option, correct usage:\r\n```" + server_help_array()["stats"] + "```")
            return
        if (datetime.datetime.utcnow() - stats_command_last_exec < datetime.timedelta(seconds=10)):
            await message.reply( "Please wait a few seconds before using this command again.")
            return
        stats_command_last_exec = datetime.datetime.utcnow()
        opt = 0
        if (tag[2] == "ot"):
            opt = 0
        elif (tag[2] == "ct"):
            opt = 1
        elif (tag[2] == "ba"):
            opt = 2
        embed = gen_course_usage_embed(ctgp7_server, opt)
        await message.reply(embed=embed)
    elif bot_cmd == "manage_vr":
        if await staff_server_can_execute(message, bot_cmd):
            tag = get_server_bot_args(message.content)
            if (len(tag) != 5 and len(tag) != 6):
                await message.reply( "Invalid syntax, correct usage:\r\n```" + staff_server_help_array()[bot_cmd] + "```")
                return
            mode = tag[2]
            game = tag[4]
            consoleID = tag[3]
            if (consoleID.startswith("0x")):
                consoleID = consoleID[2:]
            try:
                consoleID = int(consoleID, 16)
                if (consoleID == 0):
                    raise ValueError()
            except ValueError:
                await message.reply( "Invalid console ID.")
                return
            if mode not in ["get", "set"]:
                await message.reply( "Invalid option `{}`, correct usage:\r\n```".format( mode) + staff_server_help_array()[bot_cmd] + "```")
                return
            if game not in ["ctww", "cd"]:
                await message.reply( "Invalid option `{}`, correct usage:\r\n```".format( mode) + staff_server_help_array()[bot_cmd] + "```")
                return
            if (mode == "get"):
                vrData = ctgp7_server.database.get_console_vr(consoleID)
                vr = vrData[0 if game == "ctww" else 1]
                await message.reply("Console has {} VR in {}".format(vr, "Custom Tracks" if game == "ctww" else "Countdown"))
            else:
                if (len(tag) != 6):
                    await message.reply( "Invalid option `{}`, correct usage:\r\n```".format( mode) + staff_server_help_array()[bot_cmd] + "```")
                    return
                try:
                    vr = int(tag[5])
                    if (vr < 1 or vr > 99999):
                        raise ValueError()
                except ValueError:
                    await message.reply( "Invalid number.")
                    return
                vrData = list(ctgp7_server.database.get_console_vr(consoleID))
                vrData[0 if game == "ctww" else 1] = vr
                ctgp7_server.database.set_console_vr(consoleID, tuple(vrData))
                await message.reply( "Operation succeeded.")
    else:
        await message.reply( "Invalid server command, use `@RedYoshiBot server help` to get all the available server commands.")
        
def handler_server_init_loop(ctgp7_server: CTGP7ServerHandler):
    asyncio.ensure_future(server_bot_loop(ctgp7_server))