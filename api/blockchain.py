import json
import os
from web3 import Web3
from django.conf import settings


def get_contract():
    w3 = Web3(Web3.HTTPProvider(settings.SEPOLIA_RPC_URL))
    abi_path = os.path.join(os.path.dirname(__file__), 'contract_abi.json')
    with open(abi_path) as f:
        abi = json.load(f)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(settings.CONTRACT_ADDRESS),
        abi=abi,
    )
    return w3, contract


def register_batch_on_chain(batch_id, medicine_name, mfg_date, exp_date):
    """
    Register a batch on the Ethereum Sepolia testnet.
    Returns the transaction hash hex string on success.
    Raises on any failure so the caller can decide how to handle it.
    """
    w3, contract = get_contract()
    account = w3.eth.account.from_key(settings.DEPLOYER_PRIVATE_KEY)

    tx = contract.functions.registerBatch(
        str(batch_id),
        str(medicine_name),
        str(mfg_date),
        str(exp_date),
    ).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
    })

    signed_tx = w3.eth.account.sign_transaction(tx, settings.DEPLOYER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    # Confirm using the same connection — avoids load-balanced node sync lag.
    # Only block batch creation if verifyBatch explicitly returns False (wrong contract address).
    # If the read call itself raises (RPC issue), the transaction is already mined — allow it.
    try:
        confirmed = contract.functions.verifyBatch(str(batch_id)).call()
        if confirmed is False:
            raise Exception('Transaction mined but batch not found on contract — check CONTRACT_ADDRESS.')
    except Exception as e:
        if 'CONTRACT_ADDRESS' in str(e):
            raise

    return tx_hash.hex()


def verify_batch_on_chain(batch_id: str):
    """
    Call verifyBatch() on the smart contract (read-only view function — free, no gas).
    Returns True (on chain), False (not on chain), or None (network/timeout error).
    """
    try:
        w3, contract = get_contract()
        result = contract.functions.verifyBatch(str(batch_id)).call()
        return bool(result)
    except Exception:
        return None
