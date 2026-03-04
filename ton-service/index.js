/**
 * TON Blockchain Service
 * Handles all TON network interactions for Reptiloid Exchange
 * Isolated microservice for security
 */

require('dotenv').config();
const express = require('express');
const { Pool } = require('pg');
const Redis = require('redis');
const winston = require('winston');
const { v4: uuidv4 } = require('uuid');

// TON imports
const { TonClient, WalletContractV4, internal } = require('@ton/ton');
const { mnemonicNew, mnemonicToPrivateKey } = require('@ton/crypto');
const { Address, toNano, fromNano } = require('@ton/core');

// Logger setup
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: '/app/ton-service/ton-service.log' }),
    new winston.transports.File({ filename: '/app/ton-service/ton-error.log', level: 'error' }),
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    })
  ]
});

// PostgreSQL connection
const pgPool = new Pool({
  host: process.env.POSTGRES_HOST || 'localhost',
  port: process.env.POSTGRES_PORT || 5432,
  database: process.env.POSTGRES_DB || 'reptiloid_finance',
  user: process.env.POSTGRES_USER || 'finance_admin',
  password: process.env.POSTGRES_PASSWORD
});

// Redis client
let redisClient;

// TON Client
let tonClient;
let hotWallet;
let hotWalletContract;

// Express app
const app = express();
app.use(express.json());

// API Key middleware for security
const apiKeyAuth = (req, res, next) => {
  const apiKey = req.headers['x-api-key'];
  if (apiKey !== process.env.API_SECRET) {
    logger.warn(`Unauthorized API access attempt from ${req.ip}`);
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
};

/**
 * Initialize TON Client
 */
async function initTonClient() {
  const endpoint = process.env.TON_NETWORK === 'mainnet' 
    ? 'https://toncenter.com/api/v2/jsonRPC'
    : 'https://testnet.toncenter.com/api/v2/jsonRPC';
  
  tonClient = new TonClient({
    endpoint,
    apiKey: process.env.TON_API_KEY || undefined
  });
  
  logger.info(`TON Client initialized for ${process.env.TON_NETWORK}`);
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
    logger.info('No hot wallet configured. Generate one via /generate-wallet endpoint');
    return null;
  }
  
  try {
    const { wallet, keyPair, address } = await loadWallet(process.env.HOT_WALLET_MNEMONIC);
    hotWallet = { wallet, keyPair, address };
    hotWalletContract = tonClient.open(wallet);
    
    logger.info(`Hot wallet loaded: ${address}`);
    
    // Save to database
    await pgPool.query(`
      INSERT INTO wallet_config (wallet_type, address, public_key, network, is_active)
      VALUES ('hot', $1, $2, $3, true)
      ON CONFLICT (address) DO UPDATE SET is_active = true, current_seqno = wallet_config.current_seqno
    `, [address, keyPair.publicKey.toString('hex'), process.env.TON_NETWORK]);
    
    return hotWallet;
  } catch (error) {
    logger.error('Failed to load hot wallet:', error);
    return null;
  }
}

/**
 * Get wallet balance
 */
async function getWalletBalance(address) {
  try {
    const addr = Address.parse(address);
    const balance = await tonClient.getBalance(addr);
    return fromNano(balance);
  } catch (error) {
    logger.error(`Error getting balance for ${address}:`, error);
    throw error;
  }
}

/**
 * Get recent transactions for address
 */
async function getTransactions(address, limit = 20) {
  try {
    const addr = Address.parse(address);
    const transactions = await tonClient.getTransactions(addr, { limit });
    
    return transactions.map(tx => ({
      hash: tx.hash().toString('hex'),
      lt: tx.lt.toString(),
      timestamp: tx.now,
      inMessage: tx.inMessage ? {
        source: tx.inMessage.info.src?.toString(),
        value: tx.inMessage.info.type === 'internal' ? fromNano(tx.inMessage.info.value.coins) : '0',
        comment: tx.inMessage.body?.beginParse()?.loadStringTail() || null
      } : null,
      outMessages: tx.outMessages.values().map(msg => ({
        destination: msg.info.dest?.toString(),
        value: msg.info.type === 'internal' ? fromNano(msg.info.value.coins) : '0'
      }))
    }));
  } catch (error) {
    logger.error(`Error getting transactions for ${address}:`, error);
    throw error;
  }
}

/**
 * Send TON
 */
async function sendTon(toAddress, amount, comment = '') {
  if (!hotWallet) {
    throw new Error('Hot wallet not initialized');
  }
  
  try {
    const seqno = await hotWalletContract.getSeqno();
    
    await hotWalletContract.sendTransfer({
      seqno,
      secretKey: hotWallet.keyPair.secretKey,
      messages: [
        internal({
          to: toAddress,
          value: toNano(amount.toString()),
          body: comment,
          bounce: false
        })
      ]
    });
    
    // Update seqno in database
    await pgPool.query(`
      UPDATE wallet_config SET current_seqno = $1 WHERE address = $2
    `, [seqno + 1, hotWallet.address]);
    
    logger.info(`Sent ${amount} TON to ${toAddress} (seqno: ${seqno})`);
    
    // Wait a bit and check for transaction
    await new Promise(resolve => setTimeout(resolve, 10000));
    
    // Try to get tx hash (simplified - in production would poll until confirmed)
    const recentTx = await getTransactions(hotWallet.address, 5);
    const matchingTx = recentTx.find(tx => 
      tx.outMessages.some(m => m.destination === toAddress)
    );
    
    return {
      success: true,
      seqno,
      txHash: matchingTx?.hash || 'pending',
      status: matchingTx ? 'sent' : 'pending'
    };
  } catch (error) {
    logger.error(`Error sending TON to ${toAddress}:`, error);
    throw error;
  }
}

// ==================== API ENDPOINTS ====================

/**
 * Health check
 */
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    network: process.env.TON_NETWORK,
    hotWallet: hotWallet ? hotWallet.address : 'not configured'
  });
});

/**
 * Generate new wallet (for initial setup)
 */
app.post('/generate-wallet', apiKeyAuth, async (req, res) => {
  try {
    const walletData = await generateWallet();
    
    logger.info(`Generated new wallet: ${walletData.address}`);
    
    // Don't return secret key in response - save to file
    const fs = require('fs');
    fs.writeFileSync('/app/ton-service/wallet-backup.json', JSON.stringify({
      address: walletData.address,
      mnemonic: walletData.mnemonic,
      publicKey: walletData.publicKey,
      network: process.env.TON_NETWORK,
      createdAt: new Date().toISOString()
    }, null, 2));
    
    res.json({
      success: true,
      address: walletData.address,
      publicKey: walletData.publicKey,
      network: process.env.TON_NETWORK,
      message: 'IMPORTANT: Mnemonic saved to wallet-backup.json. Add to .env as HOT_WALLET_MNEMONIC and restart service.'
    });
  } catch (error) {
    logger.error('Error generating wallet:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get deposit address for user
 */
app.get('/deposit-address/:userId', apiKeyAuth, async (req, res) => {
  try {
    const { userId } = req.params;
    
    if (!hotWallet) {
      return res.status(503).json({ error: 'Hot wallet not configured' });
    }
    
    // User's unique comment for deposit identification
    const comment = userId;
    
    res.json({
      success: true,
      address: hotWallet.address,
      comment: comment,
      network: process.env.TON_NETWORK,
      message: `Send TON to this address with comment: ${comment}`
    });
  } catch (error) {
    logger.error('Error getting deposit address:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get balance of an address
 */
app.get('/balance/:address', apiKeyAuth, async (req, res) => {
  try {
    const { address } = req.params;
    const balance = await getWalletBalance(address);
    
    res.json({
      success: true,
      address,
      balance: parseFloat(balance),
      currency: 'TON'
    });
  } catch (error) {
    logger.error('Error getting balance:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get hot wallet balance
 */
app.get('/hot-wallet/balance', apiKeyAuth, async (req, res) => {
  try {
    if (!hotWallet) {
      return res.status(503).json({ error: 'Hot wallet not configured' });
    }
    
    const balance = await getWalletBalance(hotWallet.address);
    
    res.json({
      success: true,
      address: hotWallet.address,
      balance: parseFloat(balance),
      currency: 'TON'
    });
  } catch (error) {
    logger.error('Error getting hot wallet balance:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get transactions for address
 */
app.get('/transactions/:address', apiKeyAuth, async (req, res) => {
  try {
    const { address } = req.params;
    const limit = parseInt(req.query.limit) || 20;
    
    const transactions = await getTransactions(address, limit);
    
    res.json({
      success: true,
      address,
      count: transactions.length,
      transactions
    });
  } catch (error) {
    logger.error('Error getting transactions:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Send TON (withdrawal)
 */
app.post('/send-ton', apiKeyAuth, async (req, res) => {
  try {
    const { to, amount, comment, txId } = req.body;
    
    if (!to || !amount) {
      return res.status(400).json({ error: 'Missing required fields: to, amount' });
    }
    
    if (amount <= 0) {
      return res.status(400).json({ error: 'Amount must be positive' });
    }
    
    logger.info(`Withdrawal request: ${amount} TON to ${to}`);
    
    const result = await sendTon(to, amount, comment || '');
    
    res.json({
      success: true,
      txId: txId || uuidv4(),
      txHash: result.txHash,
      status: result.status,
      amount,
      to,
      fee: 0.05 // Approximate network fee
    });
  } catch (error) {
    logger.error('Error sending TON:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get user transactions from database
 */
app.get('/user-transactions/:userId', apiKeyAuth, async (req, res) => {
  try {
    const { userId } = req.params;
    const limit = parseInt(req.query.limit) || 50;
    const offset = parseInt(req.query.offset) || 0;
    
    const result = await pgPool.query(`
      SELECT * FROM transactions 
      WHERE user_id = $1 
      ORDER BY created_at DESC 
      LIMIT $2 OFFSET $3
    `, [userId, limit, offset]);
    
    res.json({
      success: true,
      userId,
      count: result.rows.length,
      transactions: result.rows
    });
  } catch (error) {
    logger.error('Error getting user transactions:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Create user finance record (called by Python backend)
 */
app.post('/create-user-finance', apiKeyAuth, async (req, res) => {
  try {
    const { userId } = req.body;
    
    if (!userId) {
      return res.status(400).json({ error: 'Missing userId' });
    }
    
    await pgPool.query(`
      INSERT INTO users_finance (user_id) 
      VALUES ($1) 
      ON CONFLICT (user_id) DO NOTHING
    `, [userId]);
    
    logger.info(`Created finance record for user: ${userId}`);
    
    res.json({ success: true, userId });
  } catch (error) {
    logger.error('Error creating user finance:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get user finance balance
 */
app.get('/user-balance/:userId', apiKeyAuth, async (req, res) => {
  try {
    const { userId } = req.params;
    
    const result = await pgPool.query(`
      SELECT * FROM users_finance WHERE user_id = $1
    `, [userId]);
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    const user = result.rows[0];
    
    res.json({
      success: true,
      userId,
      balance_ton: parseFloat(user.balance_ton),
      balance_usd: parseFloat(user.balance_usd),
      frozen_ton: parseFloat(user.frozen_ton),
      frozen_usd: parseFloat(user.frozen_usd),
      available_ton: parseFloat(user.balance_ton) - parseFloat(user.frozen_ton),
      available_usd: parseFloat(user.balance_usd) - parseFloat(user.frozen_usd)
    });
  } catch (error) {
    logger.error('Error getting user balance:', error);
    res.status(500).json({ error: error.message });
  }
});

// ==================== DEPOSIT LISTENER ====================

let lastProcessedLt = '0';
let isListenerRunning = false;

async function processDeposits() {
  if (!hotWallet || isListenerRunning) return;
  
  isListenerRunning = true;
  
  try {
    const transactions = await getTransactions(hotWallet.address, 50);
    
    for (const tx of transactions) {
      // Skip if already processed
      if (BigInt(tx.lt) <= BigInt(lastProcessedLt)) continue;
      
      // Check if this is an incoming transaction with a comment
      if (tx.inMessage && tx.inMessage.value && parseFloat(tx.inMessage.value) > 0) {
        const comment = tx.inMessage.comment;
        const amount = parseFloat(tx.inMessage.value);
        const fromAddress = tx.inMessage.source;
        
        logger.info(`Incoming deposit: ${amount} TON from ${fromAddress}, comment: ${comment}`);
        
        if (comment) {
          // Try to match comment with user_id
          const userResult = await pgPool.query(
            'SELECT * FROM users_finance WHERE user_id = $1',
            [comment]
          );
          
          if (userResult.rows.length > 0) {
            // Valid user deposit - credit balance
            const txId = uuidv4();
            
            await pgPool.query('BEGIN');
            
            try {
              // Create transaction record
              await pgPool.query(`
                INSERT INTO transactions (tx_id, user_id, type, amount, currency, tx_hash, from_address, to_address, comment, status)
                VALUES ($1, $2, 'deposit', $3, 'TON', $4, $5, $6, $7, 'success')
              `, [txId, comment, amount, tx.hash, fromAddress, hotWallet.address, comment]);
              
              // Update user balance
              await pgPool.query(`
                UPDATE users_finance 
                SET balance_ton = balance_ton + $1,
                    total_deposited_ton = total_deposited_ton + $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = $2
              `, [amount, comment]);
              
              await pgPool.query('COMMIT');
              
              logger.info(`Credited ${amount} TON to user ${comment}`);
            } catch (error) {
              await pgPool.query('ROLLBACK');
              throw error;
            }
          } else {
            // Unknown comment - flag for review
            const txId = uuidv4();
            await pgPool.query(`
              INSERT INTO transactions (tx_id, user_id, type, amount, currency, tx_hash, from_address, to_address, comment, status, error_message)
              VALUES ($1, 'unknown', 'deposit', $2, 'TON', $3, $4, $5, $6, 'review', 'Unknown user_id in comment')
            `, [txId, amount, tx.hash, fromAddress, hotWallet.address, comment]);
            
            logger.warn(`Deposit with unknown comment: ${comment}, amount: ${amount} TON`);
          }
        } else {
          // No comment - flag for review
          const txId = uuidv4();
          await pgPool.query(`
            INSERT INTO transactions (tx_id, user_id, type, amount, currency, tx_hash, from_address, to_address, status, error_message)
            VALUES ($1, 'unknown', 'deposit', $2, 'TON', $3, $4, $5, 'review', 'No comment provided')
          `, [txId, amount, tx.hash, fromAddress, hotWallet.address]);
          
          logger.warn(`Deposit without comment from ${fromAddress}, amount: ${amount} TON`);
        }
      }
      
      lastProcessedLt = tx.lt;
    }
  } catch (error) {
    logger.error('Error processing deposits:', error);
  } finally {
    isListenerRunning = false;
  }
}

// ==================== STARTUP ====================

async function startServer() {
  try {
    // Test PostgreSQL connection
    await pgPool.query('SELECT 1');
    logger.info('PostgreSQL connected');
    
    // Initialize Redis
    redisClient = Redis.createClient({
      host: process.env.REDIS_HOST,
      port: process.env.REDIS_PORT
    });
    await redisClient.connect();
    logger.info('Redis connected');
    
    // Initialize TON client
    await initTonClient();
    
    // Load hot wallet
    await initHotWallet();
    
    // Start deposit listener
    if (hotWallet) {
      setInterval(processDeposits, parseInt(process.env.DEPOSIT_POLL_INTERVAL) || 5000);
      logger.info('Deposit listener started');
    }
    
    // Start Express server
    const PORT = process.env.PORT || 8002;
    app.listen(PORT, () => {
      logger.info(`TON Service running on port ${PORT}`);
      logger.info(`Network: ${process.env.TON_NETWORK}`);
      logger.info(`Hot wallet: ${hotWallet ? hotWallet.address : 'NOT CONFIGURED'}`);
    });
    
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
