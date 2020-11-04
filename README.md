# cosmos-discord-faucet
Discord faucet bot for any blockchain based Cosmos  


<details>
  <summary>List of available commands:</summary>

1. Request coins through the faucet  
`$request sif1lj3rsayj4xtrhp2e3elv4nf7lazxty272zqegr`

Transaction status explanation:  
✅ - mean bot send transaction to your address

2. Displays the current status of the node where faucet is running  
`$faucet_status`

3. Show tap address  
`$faucet_address` or `$tap_address`

4. Show transaction information for a specific transaction ID  
`$tx_info 009CEA347EAFD795E8B10088D18156BC15F24362416BEEF1073BFDFD936E19B0`

5. Show address balance  
`$balance sif1lj3rsayj4xtrhp2e3elv4nf7lazxty272zqegr`  

</details>  


## Requirements
- python3.6+  
- Cosmos REST server (light-client daemon, a local REST server)  
- Cosmos RPC server  

## How to install  
1. Run command below  
```bash
apt update \
&& apt install -y python3-pip python3-venv git tmux \
&& git clone https://github.com/c29r3/cosmos-discord-faucet.git \
&& cd cosmos-discord-faucet \
&& python3 -m venv venv \
&& source venv/bin/activate \
&& pip3 install -r requirements.txt
```
2. [Create Discord token](https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token)  
3. Fill in config.ini  
4. Invite the bot to your channel  
5. Run REST server. Below is an example  
```bash
tmux new -s sifchain_rest -d sifnodecli rest-server --laddr tcp://localhost:1317 --node tcp://localhost:26657 --chain-id monkey-bars
```  


## How to run  
Start faucet bot  
```
tmux new -s discord_faucet_bot -d cd ~/cosmos-discord-faucet && source venv/bin/activate && python3 discord_faucet_bot.py
```  
  
### Alternatively, the bot can be run through systemd:  
- If necessary, change the username and the path to the script folder in `discord-faucet-bot.service`  

- Start the service  
```
ln -s $HOME/cosmos-discord-faucet/discord-faucet-bot.service /etc/systemd/system/ \
&& systemctl daemon-reload \
&& systemctl enable discord-faucet-bot.service \
&& systemctl start discord-faucet-bot.service \
&& systemctl status discord-faucet-bot.service
```  

