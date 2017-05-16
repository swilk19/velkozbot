import os
import time
from slackclient import SlackClient
from riotwatcher import RiotWatcher, LoLException, error_404, error_429


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
COMMAND_LIST = ["add", "print", "remove"]

#Get Rito games client
riot_token = open("riot_token","r").readline().rstrip()
riot_client = RiotWatcher(riot_token)

#Summoner/slack map
SUMMONERS = []

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
            response = print_list()
        elif current_input[0] == "print":
            response = print_list()
        else:
            response = "Could not find matching command for '" + command + "'"
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)

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