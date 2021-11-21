from asyncio import sleep
import aiofiles as aiof
import aiohttp
import discord
from cosmospy import privkey_to_address, seed_to_privkey
import configparser
import logging
import time
import datetime
import sys
import cosmos_api as api

print('Version 0.1.0')

# Turn Down Discord Logging
disc_log = logging.getLogger('discord')
disc_log.setLevel(logging.CRITICAL)

# Configure Logging
logging.basicConfig(stream=sys.stdout, level=logging.CRITICAL)
logger = logging.getLogger(__name__)

# Load config
c = configparser.ConfigParser()
c.read("config.ini", encoding='utf-8')

VERBOSE_MODE       = str(c["DEFAULT"]["verbose"])
BECH32_HRP         = str(c["CHAIN"]["BECH32_HRP"])
DECIMAL            = float(c["CHAIN"]["decimal"])
DENOMINATION_LST   = c["TX"]["denomination_list"].split(",")
AMOUNT_TO_SEND_LST = c["TX"]["amount_to_send"].split(",")
# AMOUNT_TO_SEND_LST = [AMOUNT_TO_SEND_LST[0]] + [AMOUNT_TO_SEND_LST[1]] * 33
FAUCET_SEED        = str(c["FAUCET"]["seed"])
FAUCET_PRIVKEY     = str(c["FAUCET"]["private_key"])
if FAUCET_PRIVKEY == "":
    FAUCET_PRIVKEY = str(seed_to_privkey(FAUCET_SEED).hex())
FAUCET_ADDRESS     = str(privkey_to_address(bytes.fromhex(FAUCET_PRIVKEY), hrp=BECH32_HRP))
EXPLORER_URL       = str(c["OPTIONAL"]["explorer_url"])
if EXPLORER_URL != "":
    EXPLORER_URL = f'{EXPLORER_URL}/transactions/'
REQUEST_TIMEOUT    = int(c["FAUCET"]["request_timeout"])
TOKEN              = str(c["FAUCET"]["discord_bot_token"])
LISTENING_CHANNELS = list(c["FAUCET"]["channels_to_listen"].split(","))


APPROVE_EMOJI = "✅"
REJECT_EMOJI = "🚫"
ACTIVE_REQUESTS = {}
client = discord.Client()

with open("help-msg.txt", "r", encoding="utf-8") as help_file:
    help_msg = help_file.read()


async def save_transaction_statistics(some_string: str):
    # with open("transactions.csv", "a") as csv_file:
    async with aiof.open("transactions.csv", "a") as csv_file:
        await csv_file.write(f'{some_string}\n')
        await csv_file.flush()


@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user}')


@client.event
async def on_message(message):
    session = aiohttp.ClientSession()
    message_timestamp = time.time()
    requester = message.author

    # Do not listen to your own messages
    if message.author == client.user:
        return

    if message.content.startswith('$balance'):
        address = str(message.content).replace("$balance", "").replace(" ", "").lower()
        if str(address[:3]) == BECH32_HRP and len(address) == 42:
            coins = await api.get_addr_balance(session, address)
            if len(coins) >= 1:
                await message.channel.send(f'{message.author.mention}\n'
                                           f'```{api.coins_dict_to_string(coins, headers="no")}```')

            else:
                await message.channel.send(f'{message.author.mention} account is not initialized (balance is empty)')

    if message.content.startswith('$help'):
        await message.channel.send(help_msg)

    # Show node synchronization settings
    if message.content.startswith('$faucet_status'):
        print(requester.name, "status request")
        try:
            s = await api.get_node_status(session)
            coins = await api.get_addr_balance(session, FAUCET_ADDRESS)
            seq, acc_num = await api.get_address_info(session, FAUCET_ADDRESS)
            if "node_info" in str(s) and "error" not in str(s):
                s = f'```' \
                         f'Moniker:       {s["result"]["node_info"]["moniker"]}\n' \
                         f'Address:       {FAUCET_ADDRESS}\n' \
                         f'Syncs?:        {s["result"]["sync_info"]["catching_up"]}\n' \
                         f'Last block:    {s["result"]["sync_info"]["latest_block_height"]}\n' \
                         f'Voting power:  {s["result"]["validator_info"]["voting_power"]}\n' \
                         f'Sequence:      {seq}\n' \
                         f'Coins:\n{api.coins_dict_to_string(coins, headers="no")}```'
                await message.channel.send(s)

        except Exception as statusErr:
            print(statusErr)

    if message.content.startswith('$faucet_address') or message.content.startswith('$tap_address') and message.channel.name in LISTENING_CHANNELS:
        try:
            await message.channel.send(FAUCET_ADDRESS)
        except:
            print("Can't send message $faucet_address")

    if message.content.startswith('$tx_info') and message.channel.name in LISTENING_CHANNELS:
        try:
            hash_id = str(message.content).replace("$tx_info", "").replace(" ", "")
            if len(hash_id) == 64:
                tx = await api.get_transaction_info(session, hash_id)
                if "amount" and "fee" in str(tx):
                    from_   = tx["tx"]["value"]["msg"][0]["value"]["from_address"]
                    to_     = tx["tx"]["value"]["msg"][0]["value"]["to_address"]
                    sended_coins = {}
                    for tx_ in tx["tx"]["value"]["msg"]:
                        sended_coins.update({tx_["value"]["amount"][0]["denom"]: tx_["value"]["amount"][0]["amount"]})

                    raw_log = tx["raw_log"]
                    tx = f'```' \
                         f'From:    {from_}\n' \
                         f'To:      {to_}\n' \
                         f'{api.coins_dict_to_string(sended_coins, headers="no")}```\n' \
                         f'raw_log: {raw_log[:150]}'

                    await message.channel.send(tx)
                else:
                    await message.channel.send(f'{requester.mention}, `{tx}`')
            else:
                await message.channel.send(f'Incorrect length hash id: {len(hash_id)} instead 64')

        except Exception as tx_infoErr:
            print(tx_infoErr)
            await message.channel.send(f"Can't get transaction info {tx}")

    if message.content.startswith('$request') and message.channel.name in LISTENING_CHANNELS:
        channel = message.channel
        requester_address = str(message.content).replace("$request", "").replace(" ", "").lower()

        if len(requester_address) != 42 or requester_address[:3] != BECH32_HRP:
            await channel.send(f'{requester.mention}, Invalid address format `{requester_address}`\n'
                               f'Address length must be equal 42 and the suffix must be `{BECH32_HRP}`')
            return

        if requester.id in ACTIVE_REQUESTS:
            check_time = ACTIVE_REQUESTS[requester.id]["next_request"]
            if check_time > message_timestamp:
                timeout_in_hours = int(REQUEST_TIMEOUT) / 60 / 60
                please_wait_text = f'{requester.mention}, You can request coins no more than once every {timeout_in_hours} hours.' \
                                   f'The next attempt is possible after ' \
                                   f'{round((check_time - message_timestamp) / 60, 2)} minutes'
                await channel.send(please_wait_text)
                return

            else:
                del ACTIVE_REQUESTS[requester.id]

        if requester.id not in ACTIVE_REQUESTS and requester_address not in ACTIVE_REQUESTS:

            ACTIVE_REQUESTS[requester.id] = {
                "address": requester_address,
                "requester": requester,
                "next_request": message_timestamp + REQUEST_TIMEOUT}
            print(ACTIVE_REQUESTS)

            coins = await api.get_addr_balance(session, FAUCET_ADDRESS)
            seq, acc_num = await api.get_address_info(session, FAUCET_ADDRESS)
            #print(f'{coins=} {seq=} {acc_num=}')
            coins = {i: coins[i] for i in coins if int(coins[i]) > int(AMOUNT_TO_SEND_LST[0])}

            transaction = await api.send_tx(session, recipient=requester_address,
                                            denom_lst=list(coins.keys()),
                                            amount=[AMOUNT_TO_SEND_LST[0]] * len(list(coins.keys())))
            logger.info(f'Transaction result:\n{transaction}')
            print(transaction)

            if 'code' not in str(transaction) and "txhash" in str(transaction):
                await channel.send(f'{requester.mention}, `$tx_info {EXPLORER_URL}{transaction["txhash"]}\n`')


            else:
                await channel.send(f'{requester.mention}, Can\'t send transaction. Try making another one request'
                                   f'\n{transaction}')
                del ACTIVE_REQUESTS[requester.id]

            now = datetime.datetime.now()
            await save_transaction_statistics(f'{transaction};{now.strftime("%Y-%m-%d %H:%M:%S")}')
            await session.close()

client.run(TOKEN)
