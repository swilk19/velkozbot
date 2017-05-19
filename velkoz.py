import os
import time
from slackclient import SlackClient
from riotwatcher import RiotWatcher, LoLException, error_404, error_429
#from lxml import html
#from lxml import etree
from bs4 import BeautifulSoup
import requests

# starterbot's ID as an environment variable
token_file = open("slack_token", "r")

# instantiate Slack & Twilio clients
token = token_file.readline().rstrip()
print token
slack_client = SlackClient(token)

#get Bot ID after slack token
BOT_ID = token_file.readline()
BOT_ID = BOT_ID.rstrip()
#BOT_ID = os.environ.get("BOT_ID")
print "Starting with BOT_ID = '" + BOT_ID +"'"

# constants

AT_BOT = "<@" + BOT_ID + ">"
COMMAND_LIST = ["add", "print", "remove", "pbe"]

#Get Rito games client
riot_token = open("riot_token","r").readline().rstrip()
riot_client = RiotWatcher(riot_token)
#Might as well generate a useful list once..
CHAMPION_LIST = []
champ_json = riot_client.static_get_champion_list()
champ_json = champ_json['data']
for i in champ_json:
    string_name = champ_json[i]['name'].encode('utf-8')
    CHAMPION_LIST.append(string_name.lower())


#Summoner/slack map
SUMMONERS = []

#SurrenderAt20 Current PBE Balance Changes URL
PBE_CHANGE_URL = "http://www.surrenderat20.net/p/current-pbe-balance-changes.html"

def handle_command(command, channel):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    current_input = command.split(" ")
    response = "Not sure what you mean. Currently accepted commands are: " + ", ".join(COMMAND_LIST)
    if current_input[0] in COMMAND_LIST:
        if current_input[0] == "add":
            response = add_summoner(command)
        elif current_input[0] == "remove":
            response = remove_summoner(command)
        elif current_input[0] == "print":
            response = print_list()
        elif current_input[0] == "pbe":
            response = get_pbe_changes(command)
        else:
            response = "Could not find matching command for '" + command + "'"
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)

def scrape_pbe_changes():
    #plan to accept "all", a champion name, or "items"
    print "Starting S@20 Scrap"
    page = requests.get(PBE_CHANGE_URL)
    #tree = html.fromstring(page.content)
    #soup = BeautifulSoup(etree.tostring(tree, pretty_print=True), 'html.parser')
    soup = BeautifulSoup(page.content)
    #print(etree.tostring(tree, pretty_print=True))
    #print tree
    soup = soup.find(id="news")
    #print soup.prettify()
    balance_changes = soup.h2.find_all_next(string=True)
    #get list of champions from riot, compare with elements below "balance changes"
    champion_balanace_list = {}
    #compare elements in balance_changes to the champion names. create a string of every element between champion names.
    cur_champ = ""
    done = False
    for element in balance_changes:
        encoded_element = str(element.encode('utf-8'))
        encoded_element = encoded_element.rstrip()
        if encoded_element.lower() in CHAMPION_LIST:
            cur_champ = encoded_element.lower()
            #print "Current Champ: " + cur_champ
            champion_balanace_list[cur_champ] = ""
        elif cur_champ != "":
            #if i have a current champ, add the changes i find to a string
            if not done:
                #print "Current element: " + str(encoded_element)
                if(encoded_element == "Back to Top" or encoded_element == "Items" or encoded_element == "BlogThis!"):
                    print "WE DONE FAM, element="+encoded_element
                    done = True
                else:
                    if len(encoded_element) > 2 and encoded_element != "src":
                        #fetch the current string from dict
                        cur_champ_changes = champion_balanace_list[cur_champ]
                        cur_champ_changes += encoded_element + '\n'
                        champion_balanace_list[cur_champ] = cur_champ_changes
            #update that champion's changes
    return champion_balanace_list

def get_pbe_changes(command):
    #All, Champion Name, Items e.g. pbe all, pbe illaoi, pbe items
    command_arguments = command.split(" ")
    if(len(command_arguments) > 3):
        print len(command_arguments)
        return "Wrong number of arguments, try 'pbe all' or 'pbe illaoi'"
    changes_map = scrape_pbe_changes()
    print command_arguments
    command_arguments.remove("pbe")
    argument = " ".join(command_arguments).lower()
    print argument
    print CHAMPION_LIST
    if(argument in CHAMPION_LIST):
        #get specific champ changes
        print "calling format string for " + argument
        return format_change_string(argument, changes_map)
    elif argument == "all":
        #print "Getting all changes"
        return format_change_string(changes_map.keys(), changes_map)
    else:
        return "No changes found."


def format_change_string(keys, dict):
    result_string = ""
    print type(keys)
    if isinstance(keys, unicode):
        key_str = str(keys.encode('utf-8'))
        print "looking for specific " + key_str + " among:"
        print dict.keys()
        changes = dict.get(key_str)
        if(changes == None):
            return "No changes found."
        else:
            print key_str
            print type(key_str)
            print changes
            print type(changes)
            result_string = "*" + key_str.capitalize() + "*" + '\n' + changes + '\n\n'

    else:
        for key in keys:
            print "Looking for changes for " + key
            result_string += "*" + key.capitalize() + "*" + '\n'
            result_string += dict[key] + '\n\n'
    return result_string


def print_list():
    result = []
    for summoner in SUMMONERS:
        try:
            cur_summoner = riot_client.get_summoner(name=summoner)
            cur_ranked_stats = riot_client.get_recent_games(cur_summoner['id'])
            wins = 0
            loss = 0
            recent_games = cur_ranked_stats['games']
            for game in recent_games:
                cur_game_stats = game['stats']
                if cur_game_stats['win']:
                    wins += 1
                else:
                    loss += 1
            wlratio = 100 * (float(wins) / (float(wins) + float(loss)))
            result.append(summoner + " W/L: " + str(wins) + "/" + str(loss) + " " + str(wlratio) + "%")
        except LoLException as e:
            if e == error_429:
                print('We should retry in {} seconds.'.format(e.headers['Retry-After']))
            elif e == error_404:
                print('Summoner not found: ' + summoner + ", removing from list.")
    if len(result) > 0:
        return "\n".join(result)
    else:
        return "No summoner data found."


def add_summoner(command):
    #Should go add <summoner>
    command_arguments = command.split(" ")
    if len(command_arguments) != 2:
        return "Use format add <summoner_name>"
    summoner = command_arguments[1]
    if not summoner in SUMMONERS:
        SUMMONERS.append(summoner)
        return "Added " + summoner + " to the list of summoners. Current summoner list is: " + ",".join(SUMMONERS)
    else:
        return "Summoner already exists in list: " + ", ".join(SUMMONERS)

def remove_summoner(command):
    command_arguments = command.split(" ")
    if(len(command_arguments) != 2):
        return "Use format remove <summoner_name>"
    summoner = command_arguments[1]
    if not summoner in SUMMONERS:
        return "Could not find " + summoner + " in the list. Current list: " + ", ".join(SUMMONERS)
    else:
        SUMMONERS.remove(summoner)
        return "Removed " + summoner + " from the list. Current list: " + ", ".join(SUMMONERS)



def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel']
    return None, None


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("VelKoz Bot connected and running!")
        while True:
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack slack_token or bot ID?")