import configparser
from cosmospy import Transaction, generate_wallet, privkey_to_address, seed_to_privkey

c = configparser.ConfigParser()
c.read("config.ini")

# Load data from config
VERBOSE_MODE      = str(c["DEFAULT"]["verbose"])
REST_PROVIDER     = str(c["REST"]["provider"])
RPC_PROVIDER      = str(c["RPC"]["provider"])
CHAIN_ID          = str(c["CHAIN"]["id"])
DENOMINATION      = str(c["CHAIN"]["denomination"])
BECH32_HRP        = str(c["CHAIN"]["BECH32_HRP"])
GAS_PRICE         = int(c["TX"]["gas_price"])
GAS_LIMIT         = int(c["TX"]["gas_limit"])
AMOUNT_TO_SEND    = int(c["TX"]["amount_to_send"])
FAUCET_PRIVKEY    = str(c["FAUCET"]["private_key"])
FAUCET_SEED       = str(c["FAUCET"]["seed"])
if FAUCET_PRIVKEY == "":
    FAUCET_PRIVKEY = str(seed_to_privkey(FAUCET_SEED).hex())

FAUCET_ADDRESS    = str(privkey_to_address(bytes.fromhex(FAUCET_PRIVKEY), hrp=BECH32_HRP))
EXPLORER_URL      = str(c["OPTIONAL"]["explorer_url"])


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
        print(await resp.text())
        return f'error: in async_request()\n{url} {err}'


async def get_address_info(session, addr: str):
    try:
        """:returns sequence: int, account_number: int, balance: int"""
        d = await async_request(session, url=f'{REST_PROVIDER}/auth/accounts/{addr}')
        if "amount" in str(d):
            acc_num = int(d["result"]["value"]["account_number"])
            seq     = int(d["result"]["value"]["sequence"])
            balance = int(d["result"]["value"]["coins"][0]["amount"])
            return seq, acc_num, balance
        else:
            print(d)
            return 0, 0, 0

    except Exception as address_info_err:
        if VERBOSE_MODE == "yes":
            print(address_info_err)
        return 0, 0, 0


async def get_node_status(session):
    url = f'{RPC_PROVIDER}/status'
    return await async_request(session, url=url)


async def get_transaction_info(session, trans_id_hex: str):
    # if trans_id_hex[0:2] != "0x":
    #     trans_id_hex = f'0x{trans_id_hex}'

    url = f'{REST_PROVIDER}/txs/{trans_id_hex}'
    resp = await async_request(session, url=url)
    if 'height' in str(resp):
        return resp
    else:
        return f"error: {trans_id_hex} not found"


async def send_tx(session, recipient: str) -> str:
    url_ = f'{REST_PROVIDER}/txs'
    try:
        sequence, acc_number, balance = await get_address_info(session, FAUCET_ADDRESS)
        txs = await gen_transaction(recipient_=recipient, sequence=sequence, account_num=acc_number)
        pushable_tx = txs.get_pushable()
        result = async_request(session, url=url_, data=pushable_tx)
        return await result

    except Exception as reqErrs:
        if VERBOSE_MODE == "yes":
            print(f'error in send_txs() {REST_PROVIDER}: {reqErrs}')


async def gen_transaction(recipient_: str, sequence: int, account_num: int, priv_key: str = FAUCET_PRIVKEY,
                          gas: int = GAS_LIMIT, memo: str = "", chain_id_: str = CHAIN_ID, denom: str = DENOMINATION,
                          amount_: int = AMOUNT_TO_SEND, fee: int = GAS_PRICE):

    tx = Transaction(
        privkey=bytes.fromhex(priv_key),
        account_num=account_num,
        sequence=sequence,
        fee_denom=denom,
        fee=fee,
        gas=gas,
        memo=memo,
        chain_id=chain_id_,
        hrp=BECH32_HRP,
        sync_mode="sync"
    )
    tx.add_transfer(recipient=recipient_, amount=amount_, denom=denom)
    return tx


def gen_keypair():
    """:returns address: str, private_key: str, seed: str"""
    new_wallet = generate_wallet(hrp=BECH32_HRP)
    return new_wallet["address"], new_wallet["private_key"].hex(), new_wallet["seed"]


