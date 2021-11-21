import configparser
from tabulate import tabulate
from cosmospy import Transaction, generate_wallet, privkey_to_address, seed_to_privkey

c = configparser.ConfigParser()
c.read("config.ini", encoding='utf-8')

# Load data from config
VERBOSE_MODE          = str(c["DEFAULT"]["verbose"])
DECIMAL               = float(c["CHAIN"]["decimal"])
REST_PROVIDER         = str(c["REST"]["provider"])
MAIN_DENOM            = str(c["CHAIN"]["denomination"])
RPC_PROVIDER          = str(c["RPC"]["provider"])
CHAIN_ID              = str(c["CHAIN"]["id"])
BECH32_HRP            = str(c["CHAIN"]["BECH32_HRP"])
GAS_PRICE             = int(c["TX"]["gas_price"])
GAS_LIMIT             = int(c["TX"]["gas_limit"])
FAUCET_PRIVKEY        = str(c["FAUCET"]["private_key"])
FAUCET_SEED           = str(c["FAUCET"]["seed"])
if FAUCET_PRIVKEY == "":
    FAUCET_PRIVKEY = str(seed_to_privkey(FAUCET_SEED).hex())

FAUCET_ADDRESS    = str(privkey_to_address(bytes.fromhex(FAUCET_PRIVKEY), hrp=BECH32_HRP))
EXPLORER_URL      = str(c["OPTIONAL"]["explorer_url"])


def coins_dict_to_string(coins: dict, table_fmt_: str = "", headers="") -> str:
    if headers == "":
        headers = ["Token", "Amount (wei)", "amount / decimal"]

    hm = []
    """
    :param table_fmt_: grid | pipe | html
    :param coins: {'clink': '100000000000000000000', 'chot': '100000000000000000000'}
    :return: str
    """
    for i in range(len(coins)):
        hm.append([list(coins.keys())[i], list(coins.values())[i], int(int(list(coins.values())[i]) / DECIMAL)])

    print(coins)
    if headers == "no":
        d = tabulate(hm, tablefmt=table_fmt_)
    else:
        d = tabulate(hm, tablefmt=table_fmt_, headers=headers)
    return d


async def async_request(session, url, data: str = ""):
    headers = {"Content-Type": "application/json"}
    try:
        if data == "":
            async with session.get(url=url, headers=headers) as resp:
                data = await resp.text()
        else:
            async with session.post(url=url, data=data, headers=headers) as resp:
                data = await resp.text()

        if type(data) is None or "error" in data:
            return await resp.text()
        else:
            return await resp.json()

    except Exception as err:
        return f'error: in async_request()\n{url} {err}'


async def get_addr_balance(session, addr: str):
    d = ""
    coins = {}
    try:
        d = await async_request(session, url=f'{REST_PROVIDER}/cosmos/bank/v1beta1/balances/{addr}')
        if "balances" in str(d):
            for i in d["balances"]:
                coins[i["denom"]] = i["amount"]
            return coins
        else:
            return 0
    except Exception as addr_balancer_err:
        print("get_addr_balance", d, addr_balancer_err)


async def get_address_info(session, addr: str):
    try:
        """:returns sequence: int, account_number: int, coins: dict"""
        d = await async_request(session, url=f'{REST_PROVIDER}/auth/accounts/{addr}')
        print(d)

        if "result" in str(d):
            acc_num = int(d["result"]["value"]["account_number"])
            try:
                seq     = int(d["result"]["value"]["sequence"]) or 0
            except:
                seq = 0
            return seq, acc_num

    except Exception as address_info_err:
        if VERBOSE_MODE == "yes":
            print(address_info_err)
        return 0, 0


async def get_node_status(session):
    url = f'{RPC_PROVIDER}/status'
    return await async_request(session, url=url)


async def get_transaction_info(session, trans_id_hex: str):
    url = f'{REST_PROVIDER}/txs/{trans_id_hex}'
    resp = await async_request(session, url=url)
    if 'height' in str(resp):
        return resp
    else:
        return f"error: {trans_id_hex} not found"


async def send_tx(session, recipient: str, denom_lst: list, amount: list) -> str:
    url_ = f'{REST_PROVIDER}/txs'
    try:
        sequence, acc_number = await get_address_info(session, FAUCET_ADDRESS)
        txs = await gen_transaction(recipient_=recipient, sequence=sequence,
                                    account_num=acc_number, denom=denom_lst, amount_=amount)
        pushable_tx = txs.get_pushable()
        result = async_request(session, url=url_, data=pushable_tx)
        return await result

    except Exception as reqErrs:
        if VERBOSE_MODE == "yes":
            print(f'error in send_txs() {REST_PROVIDER}: {reqErrs}')
        return f"error: {reqErrs}"


async def gen_transaction(recipient_: str, sequence: int, denom: list, account_num: int, amount_: list,
                          gas: int = GAS_LIMIT, memo: str = "", chain_id_: str = CHAIN_ID,
                          fee: int = GAS_PRICE, priv_key: str = FAUCET_PRIVKEY):

    tx = Transaction(
        privkey=bytes.fromhex(priv_key),
        account_num=account_num,
        sequence=sequence,
        fee_denom=MAIN_DENOM,
        fee=fee,
        gas=gas,
        memo=memo,
        chain_id=chain_id_,
        hrp=BECH32_HRP,
        sync_mode="sync"
    )
    if type(denom) is list:
        for i, den in enumerate(denom):
            tx.add_transfer(recipient=recipient_, amount=amount_[i], denom=den)

    else:
        tx.add_transfer(recipient=recipient_, amount=amount_[0], denom=denom[0])
    return tx


def gen_keypair():
    """:returns address: str, private_key: str, seed: str"""
    new_wallet = generate_wallet(hrp=BECH32_HRP)
    return new_wallet["address"], new_wallet["private_key"].hex(), new_wallet["seed"]
