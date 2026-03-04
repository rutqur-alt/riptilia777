/**
 * TON Blockchain Service
 * Handles all TON network interactions for Reptiloid Exchange
 * Uses MongoDB for balance storage (synced with main backend)
 */

require('dotenv').config();
const express = require('express');
const { MongoClient } = require('mongodb');
const winston = require('winston');
const { v4: uuidv4 } = require('uuid');

// TON imports
const { TonClient, WalletContractV4, internal } = require('@ton/ton');
const { mnemonicNew, mnemonicToPrivateKey } = require('@ton/crypto');
const { Address, toNano, fromNano, beginCell } = require('@ton/core');

// Logger setup
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: '/app/ton-service/ton-service.log', maxsize: 5242880, maxFiles: 3 }),
    new winston.transports.File({ filename: '/app/ton-service/ton-error.log', level: 'error', maxsize: 5242880, maxFiles: 3 }),
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    })
  ]
});

// MongoDB connection
let mongoClient = null;
let db = null;
let mongoConnected = false;

// TON Client
let tonClient;
let hotWallet;
let hotWalletContract;

// Rate limiting tracking
let lastApiCall = 0;
const MIN_API_INTERVAL = 2000;
let consecutiveErrors = 0;
const MAX_CONSECUTIVE_ERRORS = 5;

// Express app
const app = express();
app.use(express.json());

// API Key middleware
const apiKeyAuth = (req, res, next) => {
  const apiKey = req.headers['x-api-key'];
  if (apiKey !== process.env.API_SECRET) {
    logger.warn(`Unauthorized API access attempt from ${req.ip}`);
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
};

/**
 * Rate limit helper
 */
async function waitForRateLimit() {
  const now = Date.now();
  const timeSinceLastCall = now - lastApiCall;
  const backoffMultiplier = Math.pow(2, Math.min(consecutiveErrors, 5));
  const requiredInterval = MIN_API_INTERVAL * backoffMultiplier;
  
  if (timeSinceLastCall < requiredInterval) {
    const waitTime = requiredInterval - timeSinceLastCall;
    await new Promise(resolve => setTimeout(resolve, waitTime));
  }
  
  lastApiCall = Date.now();
}

/**
 * Initialize MongoDB connection
 */
async function initMongoDB() {
  try {
    const mongoUrl = process.env.MONGO_URL || 'mongodb://localhost:27017';
    const dbName = process.env.DB_NAME || 'test_database';
    
    mongoClient = new MongoClient(mongoUrl);
    await mongoClient.connect();
    db = mongoClient.db(dbName);
    
    // Test connection
    await db.command({ ping: 1 });
    mongoConnected = true;
    
    logger.info(`MongoDB connected to database: ${dbName}`);
    return true;
  } catch (error) {
    logger.error('MongoDB connection failed:', error.message);
    mongoConnected = false;
    return false;
  }
}

/**
 * Initialize TON Client
 */
async function initTonClient() {
  const endpoint = process.env.TON_NETWORK === 'mainnet' 
    ? 'https://toncenter.com/api/v2/jsonRPC'
    : 'https://testnet.toncenter.com/api/v2/jsonRPC';
  
  const config = { endpoint };
  
  if (process.env.TON_API_KEY) {
    config.apiKey = process.env.TON_API_KEY;
  }
  
  tonClient = new TonClient(config);
  logger.info(`TON Client initialized for ${process.env.TON_NETWORK}${process.env.TON_API_KEY ? ' with API key' : ' without API key'}`);
}

/**
 * Generate new wallet
 */
async function generateWallet() {
  const mnemonic = await mnemonicNew(24);
  const keyPair = await mnemonicToPrivateKey(mnemonic);
  
  const wallet = WalletContractV4.create({
    workchain: 0,
    publicKey: keyPair.publicKey
  });
  
  return {
    mnemonic: mnemonic.join(' '),
    address: wallet.address.toString({ testOnly: process.env.TON_NETWORK === 'testnet' }),
    publicKey: keyPair.publicKey.toString('hex'),
    secretKey: keyPair.secretKey.toString('hex')
  };
}

/**
 * Load wallet from mnemonic
 */
async function loadWallet(mnemonic) {
  const mnemonicArray = mnemonic.split(' ');
  const keyPair = await mnemonicToPrivateKey(mnemonicArray);
  
  const wallet = WalletContractV4.create({
    workchain: 0,
    publicKey: keyPair.publicKey
  });
  
  return {
    wallet,
    keyPair,
    address: wallet.address.toString({ testOnly: process.env.TON_NETWORK === 'testnet' })
  };
}

/**
 * Initialize hot wallet
 */
async function initHotWallet() {
  if (!process.env.HOT_WALLET_MNEMONIC) {
    logger.info('No hot wallet configured');
    return null;
  }
  
  try {
    const { wallet, keyPair, address } = await loadWallet(process.env.HOT_WALLET_MNEMONIC);
    hotWallet = { wallet, keyPair, address };
    hotWalletContract = tonClient.open(wallet);
    
    logger.info(`Hot wallet loaded: ${address}`);
    return hotWallet;
  } catch (error) {
    logger.error('Failed to load hot wallet:', error);
    return null;
  }
}

/**
 * Get wallet TON balance
 */
async function getWalletBalance(address, retries = 3) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      await waitForRateLimit();
      const addr = Address.parse(address);
      const balance = await tonClient.getBalance(addr);
      consecutiveErrors = 0;
      return fromNano(balance);
    } catch (error) {
      consecutiveErrors++;
      
      if (error.message?.includes('429') || error.response?.status === 429) {
        logger.warn(`Rate limited (attempt ${attempt + 1}/${retries}), waiting...`);
        await new Promise(resolve => setTimeout(resolve, 5000 * (attempt + 1)));
        continue;
      }
      
      if (attempt === retries - 1) {
        logger.error(`Error getting balance for ${address}:`, error.message);
        throw error;
      }
    }
  }
}

/**
 * Get USDT Jetton balance
 */
async function getUSDTBalance(walletAddress, retries = 3) {
  const USDT_MASTER = process.env.TON_NETWORK === 'mainnet' 
    ? 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs'
    : 'kQBqSpvo4S87mX9tjHaG4zhYZeORhVhMapBJpnMZ64jhrP-A';
  
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      await waitForRateLimit();
      
      const ownerAddress = Address.parse(walletAddress);
      const jettonMaster = Address.parse(USDT_MASTER);
      
      const result = await tonClient.runMethod(jettonMaster, 'get_wallet_address', [
        { type: 'slice', cell: beginCell().storeAddress(ownerAddress).endCell() }
      ]);
      
      const jettonWalletAddress = result.stack.readAddress();
      
      try {
        const balanceResult = await tonClient.runMethod(jettonWalletAddress, 'get_wallet_data', []);
        const balance = balanceResult.stack.readBigNumber();
        return Number(balance) / 1000000; // USDT has 6 decimals
      } catch (e) {
        return 0;
      }
    } catch (error) {
      consecutiveErrors++;
      
      if (error.message?.includes('429') || error.response?.status === 429) {
        logger.warn(`Rate limited on USDT balance (attempt ${attempt + 1}/${retries}), waiting...`);
        await new Promise(resolve => setTimeout(resolve, 5000 * (attempt + 1)));
        continue;
      }
      
      if (attempt === retries - 1) {
        logger.error(`Error getting USDT balance for ${walletAddress}:`, error.message);
        return 0;
      }
    }
  }
  return 0;
}

/**
 * Get recent transactions
 */
async function getTransactions(address, limit = 20, retries = 3) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      await waitForRateLimit();
      const addr = Address.parse(address);
      const transactions = await tonClient.getTransactions(addr, { limit });
      consecutiveErrors = 0;
      
      return transactions.map(tx => ({
        hash: tx.hash().toString('hex'),
        lt: tx.lt.toString(),
        timestamp: tx.now,
        inMessage: tx.inMessage ? {
          source: tx.inMessage.info.src?.toString(),
          value: tx.inMessage.info.type === 'internal' ? fromNano(tx.inMessage.info.value.coins) : '0',
          comment: (() => {
            try {
              return tx.inMessage.body?.beginParse()?.loadStringTail() || null;
            } catch {
              return null;
            }
          })()
        } : null,
        outMessages: tx.outMessages.values().map(msg => ({
          destination: msg.info.dest?.toString(),
          value: msg.info.type === 'internal' ? fromNano(msg.info.value.coins) : '0'
        }))
      }));
    } catch (error) {
      consecutiveErrors++;
      
      if (error.message?.includes('429') || error.response?.status === 429) {
        logger.warn(`Rate limited on transactions (attempt ${attempt + 1}/${retries}), waiting...`);
        await new Promise(resolve => setTimeout(resolve, 5000 * (attempt + 1)));
        continue;
      }
      
      if (attempt === retries - 1) {
        logger.error(`Error getting transactions for ${address}:`, error.message);
        throw error;
      }
    }
  }
}

/**
 * Send TON
 */
async function sendTon(toAddress, amount, comment = '') {
  if (!hotWallet) {
    throw new Error('Hot wallet not initialized');
  }
  
  await waitForRateLimit();
  
  const seqno = await hotWalletContract.getSeqno();
  
  await hotWalletContract.sendTransfer({
    seqno,
    secretKey: hotWallet.keyPair.secretKey,
    messages: [
      internal({
        to: Address.parse(toAddress),
        value: toNano(amount.toString()),
        body: comment
      })
    ]
  });
  
  return {
    success: true,
    seqno,
    amount,
    to: toAddress
  };
}

// ==================== API ENDPOINTS ====================

app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    network: process.env.TON_NETWORK,
    hotWallet: hotWallet?.address || null,
    mongodb: mongoConnected ? 'connected' : 'disconnected',
    timestamp: new Date().toISOString()
  });
});

app.post('/generate-wallet', apiKeyAuth, async (req, res) => {
  try {
    const wallet = await generateWallet();
    logger.info(`New wallet generated: ${wallet.address}`);
    res.json(wallet);
  } catch (error) {
    logger.error('Error generating wallet:', error);
    res.status(500).json({ error: error.message });
  }
});

app.get('/balance/:address', apiKeyAuth, async (req, res) => {
  try {
    const tonBalance = await getWalletBalance(req.params.address);
    const usdtBalance = await getUSDTBalance(req.params.address);
    
    res.json({
      address: req.params.address,
      ton_balance: parseFloat(tonBalance),
      usdt_balance: usdtBalance,
      network: process.env.TON_NETWORK
    });
  } catch (error) {
    logger.error('Error getting balance:', error);
    res.status(500).json({ error: error.message });
  }
});

app.get('/hot-wallet/balance', apiKeyAuth, async (req, res) => {
  try {
    if (!hotWallet) {
      return res.status(400).json({ error: 'Hot wallet not configured' });
    }
    
    const tonBalance = await getWalletBalance(hotWallet.address);
    const usdtBalance = await getUSDTBalance(hotWallet.address);
    
    res.json({
      address: hotWallet.address,
      ton_balance: parseFloat(tonBalance),
      usdt_balance: usdtBalance,
      network: process.env.TON_NETWORK
    });
  } catch (error) {
    logger.error('Error getting hot wallet balance:', error);
    res.status(500).json({ error: error.message });
  }
});

app.get('/deposit-address/:userId', apiKeyAuth, async (req, res) => {
  try {
    if (!hotWallet) {
      return res.status(400).json({ error: 'Hot wallet not configured' });
    }
    
    res.json({
      address: hotWallet.address,
      comment: req.params.userId,
      network: process.env.TON_NETWORK,
      instructions: 'Send USDT (TON network) with comment = your user ID'
    });
  } catch (error) {
    logger.error('Error getting deposit address:', error);
    res.status(500).json({ error: error.message });
  }
});

app.get('/transactions/:address', apiKeyAuth, async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 20;
    const transactions = await getTransactions(req.params.address, limit);
    res.json({ transactions });
  } catch (error) {
    logger.error('Error getting transactions:', error);
    res.status(500).json({ error: error.message });
  }
});

app.post('/send', apiKeyAuth, async (req, res) => {
  try {
    const { to, amount, comment } = req.body;
    
    if (!to || !amount) {
      return res.status(400).json({ error: 'Missing to or amount' });
    }
    
    const result = await sendTon(to, amount, comment || '');
    logger.info(`Sent ${amount} TON to ${to}`);
    res.json(result);
  } catch (error) {
    logger.error('Error sending TON:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Send USDT (Jetton) to address
 */
app.post('/send-usdt', apiKeyAuth, async (req, res) => {
  try {
    const { to, amount, comment } = req.body;
    
    if (!to || !amount) {
      return res.status(400).json({ error: 'Missing to or amount' });
    }
    
    if (!hotWallet) {
      return res.status(400).json({ error: 'Hot wallet not configured' });
    }
    
    // USDT has 6 decimals
    const usdtAmount = BigInt(Math.floor(amount * 1000000));
    
    // Get hot wallet's jetton wallet address
    const USDT_MASTER = process.env.TON_NETWORK === 'mainnet' 
      ? 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs'
      : 'kQBqSpvo4S87mX9tjHaG4zhYZeORhVhMapBJpnMZ64jhrP-A';
    
    const ownerAddress = Address.parse(hotWallet.address);
    const jettonMaster = Address.parse(USDT_MASTER);
    
    // Get our jetton wallet address
    const jettonWalletResult = await tonClient.runMethod(jettonMaster, 'get_wallet_address', [
      { type: 'slice', cell: beginCell().storeAddress(ownerAddress).endCell() }
    ]);
    const jettonWalletAddress = jettonWalletResult.stack.readAddress();
    
    // Build jetton transfer message
    // op code for jetton transfer = 0xf8a7ea5
    const forwardPayload = comment 
      ? beginCell().storeUint(0, 32).storeStringTail(comment).endCell()
      : null;
    
    const jettonTransferBody = beginCell()
      .storeUint(0xf8a7ea5, 32) // op code for jetton transfer
      .storeUint(0, 64) // query_id
      .storeCoins(usdtAmount) // amount of jettons
      .storeAddress(Address.parse(to)) // destination
      .storeAddress(ownerAddress) // response_destination
      .storeBit(false) // no custom_payload
      .storeCoins(toNano('0.01')) // forward_ton_amount
      .storeMaybeRef(forwardPayload) // forward_payload
      .endCell();
    
    // Send transaction
    await waitForRateLimit();
    const seqno = await hotWalletContract.getSeqno();
    
    await hotWalletContract.sendTransfer({
      seqno,
      secretKey: hotWallet.keyPair.secretKey,
      messages: [
        internal({
          to: jettonWalletAddress,
          value: toNano('0.05'), // Gas for jetton transfer
          body: jettonTransferBody
        })
      ]
    });
    
    // Wait a bit and try to get the transaction hash
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Get recent transactions to find our tx
    let txHash = null;
    try {
      const transactions = await tonClient.getTransactions(ownerAddress, { limit: 5 });
      for (const tx of transactions) {
        if (tx.now > Date.now() / 1000 - 60) { // Within last minute
          txHash = tx.hash().toString('hex');
          break;
        }
      }
    } catch (e) {
      logger.warn('Could not get tx hash:', e.message);
    }
    
    logger.info(`✅ Sent ${amount} USDT to ${to}, seqno: ${seqno}, hash: ${txHash || 'pending'}`);
    
    res.json({
      success: true,
      seqno,
      amount,
      to,
      tx_hash: txHash,
      network: process.env.TON_NETWORK
    });
    
  } catch (error) {
    logger.error('Error sending USDT:', error);
    res.status(500).json({ error: error.message });
  }
});

// ==================== USDT DEPOSIT LISTENER ====================

// Track processed transactions to avoid duplicates
let processedTxHashes = new Set();
let lastCheckedLt = '0';
let isListenerRunning = false;

// USDT Master address on mainnet
const USDT_MASTER_MAINNET = 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs';

/**
 * Get USDT Jetton wallet address for hot wallet
 */
async function getHotWalletJettonAddress() {
  try {
    const ownerAddress = Address.parse(hotWallet.address);
    const jettonMaster = Address.parse(USDT_MASTER_MAINNET);
    
    const result = await tonClient.runMethod(jettonMaster, 'get_wallet_address', [
      { type: 'slice', cell: beginCell().storeAddress(ownerAddress).endCell() }
    ]);
    
    return result.stack.readAddress();
  } catch (error) {
    logger.error('Error getting jetton wallet address:', error.message);
    return null;
  }
}

/**
 * Parse USDT transfer from transaction
 */
function parseJettonTransfer(tx) {
  try {
    if (!tx.inMessage || !tx.inMessage.body) return null;
    
    const slice = tx.inMessage.body.beginParse();
    const op = slice.loadUint(32);
    
    // op code for jetton transfer notification = 0x7362d09c
    if (op !== 0x7362d09c) return null;
    
    const queryId = slice.loadUint(64);
    const amount = slice.loadCoins();
    const sender = slice.loadAddress();
    
    // Try to load forward payload (comment)
    let comment = null;
    try {
      const forwardPayload = slice.loadMaybeRef();
      if (forwardPayload) {
        const payloadSlice = forwardPayload.beginParse();
        const textOp = payloadSlice.loadUint(32);
        if (textOp === 0) {
          comment = payloadSlice.loadStringTail();
        }
      }
    } catch (e) {
      // No comment
    }
    
    return {
      amount: Number(amount) / 1000000, // USDT has 6 decimals
      sender: sender.toString(),
      comment
    };
  } catch (error) {
    return null;
  }
}

/**
 * Find user by deposit code or ID in MongoDB (traders or merchants)
 */
async function findUserByCode(code) {
  if (!mongoConnected || !db) return null;
  
  // Try by short deposit_code first (6 digits)
  let user = await db.collection('traders').findOne({ deposit_code: code });
  if (user) return { user, collection: 'traders' };
  
  user = await db.collection('merchants').findOne({ deposit_code: code });
  if (user) return { user, collection: 'merchants' };
  
  // Fallback: try by full user ID (for backwards compatibility)
  user = await db.collection('traders').findOne({ id: code });
  if (user) return { user, collection: 'traders' };
  
  user = await db.collection('merchants').findOne({ id: code });
  if (user) return { user, collection: 'merchants' };
  
  return null;
}

/**
 * Credit USDT to user balance
 */
async function creditUserBalance(code, amount, txHash, fromAddress) {
  if (!mongoConnected || !db) {
    logger.error('MongoDB not connected, cannot credit balance');
    return false;
  }
  
  try {
    const userInfo = await findUserByCode(code);
    
    if (!userInfo) {
      logger.warn(`User not found for deposit code: ${code}, amount: ${amount} USDT`);
      return false;
    }
    
    const { user, collection } = userInfo;
    
    // Update balance
    const result = await db.collection(collection).updateOne(
      { id: user.id },
      { $inc: { balance_usdt: amount } }
    );
    
    if (result.modifiedCount === 0) {
      logger.error(`Failed to credit balance for user ${user.id}`);
      return false;
    }
    
    // Create transaction record
    const txRecord = {
      id: `dep_${uuidv4().replace(/-/g, '').slice(0, 12)}`,
      user_id: user.id,
      type: 'deposit',
      amount: amount,
      currency: 'USDT',
      status: 'completed',
      tx_hash: txHash,
      from_address: fromAddress,
      to_address: hotWallet.address,
      created_at: new Date().toISOString(),
      description: `Пополнение ${amount} USDT`
    };
    
    await db.collection('transactions').insertOne(txRecord);
    
    logger.info(`✅ CREDITED ${amount} USDT to ${collection} ${user.login || user.id} (code: ${code})`);
    return true;
  } catch (error) {
    logger.error(`Error crediting balance: ${error.message}`);
    return false;
  }
}

/**
 * Process incoming USDT deposits
 */
async function processUSDTDeposits() {
  if (!hotWallet || isListenerRunning || !mongoConnected) return;
  
  if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
    logger.warn(`Skipping deposit check due to ${consecutiveErrors} consecutive errors`);
    consecutiveErrors = Math.max(0, consecutiveErrors - 1); // Slowly recover
    return;
  }
  
  isListenerRunning = true;
  
  try {
    // Get jetton wallet address
    const jettonWalletAddress = await getHotWalletJettonAddress();
    if (!jettonWalletAddress) {
      logger.warn('Could not get jetton wallet address');
      isListenerRunning = false;
      return;
    }
    
    // Get transactions to jetton wallet
    await waitForRateLimit();
    const transactions = await tonClient.getTransactions(jettonWalletAddress, { limit: 30 });
    
    for (const tx of transactions) {
      const txHash = tx.hash().toString('hex');
      
      // Skip already processed
      if (processedTxHashes.has(txHash)) continue;
      
      // Parse jetton transfer
      const transfer = parseJettonTransfer(tx);
      
      if (transfer && transfer.amount > 0 && transfer.comment) {
        logger.info(`📥 Incoming USDT: ${transfer.amount} from ${transfer.sender}, comment: "${transfer.comment}"`);
        
        // Credit to user balance
        const credited = await creditUserBalance(
          transfer.comment, // comment = user_id
          transfer.amount,
          txHash,
          transfer.sender
        );
        
        if (!credited) {
          logger.warn(`Could not credit deposit to user: ${transfer.comment}`);
        }
      }
      
      // Mark as processed
      processedTxHashes.add(txHash);
      
      // Cleanup old hashes (keep last 1000)
      if (processedTxHashes.size > 1000) {
        const arr = Array.from(processedTxHashes);
        processedTxHashes = new Set(arr.slice(-500));
      }
    }
    
    consecutiveErrors = 0;
  } catch (error) {
    consecutiveErrors++;
    logger.error('Error processing USDT deposits:', error.message);
  } finally {
    isListenerRunning = false;
  }
}

/**
 * Also check TON deposits with comments (fallback)
 */
async function processTONDeposits() {
  if (!hotWallet || !mongoConnected) return;
  
  try {
    const transactions = await getTransactions(hotWallet.address, 20);
    
    for (const tx of transactions) {
      if (processedTxHashes.has(tx.hash)) continue;
      
      // Check incoming TON with comment
      if (tx.inMessage && tx.inMessage.comment && parseFloat(tx.inMessage.value) > 0.01) {
        const comment = tx.inMessage.comment;
        const tonAmount = parseFloat(tx.inMessage.value);
        
        // For now, log TON deposits (could convert to USDT value)
        logger.info(`📥 Incoming TON: ${tonAmount} TON, comment: "${comment}"`);
        
        // We only credit USDT deposits, TON is for fees
      }
      
      processedTxHashes.add(tx.hash);
    }
  } catch (error) {
    // Silent fail for TON deposits
  }
}

// ==================== STARTUP ====================

async function startServer() {
  try {
    // Initialize MongoDB (required)
    const mongoOk = await initMongoDB();
    if (!mongoOk) {
      logger.error('MongoDB connection required! Check MONGO_URL and DB_NAME env vars');
      process.exit(1);
    }
    
    // Initialize TON client
    await initTonClient();
    
    // Load hot wallet
    await initHotWallet();
    
    // Start deposit listener
    if (hotWallet && mongoConnected) {
      const pollInterval = parseInt(process.env.DEPOSIT_POLL_INTERVAL) || 30000;
      
      // Run deposit checks
      setInterval(processUSDTDeposits, pollInterval);
      setInterval(processTONDeposits, pollInterval * 2); // Less frequent for TON
      
      logger.info(`💰 USDT Deposit listener started (interval: ${pollInterval}ms)`);
      
      // Run first check after 5 seconds
      setTimeout(processUSDTDeposits, 5000);
    }
    
    // Start Express server
    const PORT = process.env.PORT || 8002;
    app.listen(PORT, '0.0.0.0', () => {
      logger.info(`\n========================================`);
      logger.info(`TON Service running on port ${PORT}`);
      logger.info(`Network: ${process.env.TON_NETWORK}`);
      logger.info(`Hot wallet: ${hotWallet ? hotWallet.address : 'NOT CONFIGURED'}`);
      logger.info(`MongoDB: ${mongoConnected ? 'CONNECTED' : 'DISCONNECTED'}`);
      logger.info(`========================================\n`);
    });
    
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
