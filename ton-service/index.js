/**
 * TON Blockchain Service
 * Handles all TON network interactions for Reptiloid Exchange
 * Isolated microservice for security
 */

require('dotenv').config();
const express = require('express');
const { Pool } = require('pg');
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

// PostgreSQL connection (optional - graceful handling)
let pgPool = null;
let pgConnected = false;

// TON Client
let tonClient;
let hotWallet;
let hotWalletContract;

// Rate limiting tracking
let lastApiCall = 0;
const MIN_API_INTERVAL = 2000; // Minimum 2 seconds between API calls
let consecutiveErrors = 0;
const MAX_CONSECUTIVE_ERRORS = 5;

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
 * Rate limit helper - ensures we don't hit toncenter limits
 */
async function waitForRateLimit() {
  const now = Date.now();
  const timeSinceLastCall = now - lastApiCall;
  
  // Add exponential backoff if we've had errors
  const backoffMultiplier = Math.pow(2, Math.min(consecutiveErrors, 5));
  const requiredInterval = MIN_API_INTERVAL * backoffMultiplier;
  
  if (timeSinceLastCall < requiredInterval) {
    const waitTime = requiredInterval - timeSinceLastCall;
    await new Promise(resolve => setTimeout(resolve, waitTime));
  }
  
  lastApiCall = Date.now();
}

/**
 * Initialize TON Client with rate limiting
 */
async function initTonClient() {
  const endpoint = process.env.TON_NETWORK === 'mainnet' 
    ? 'https://toncenter.com/api/v2/jsonRPC'
    : 'https://testnet.toncenter.com/api/v2/jsonRPC';
  
  const config = { endpoint };
  
  // Add API key if available (increases rate limits significantly)
  if (process.env.TON_API_KEY) {
    config.apiKey = process.env.TON_API_KEY;
  }
  
  tonClient = new TonClient(config);
  
  logger.info(`TON Client initialized for ${process.env.TON_NETWORK}${process.env.TON_API_KEY ? ' with API key' : ' without API key (limited rate)'}`);
}

/**
 * Initialize PostgreSQL connection
 */
async function initPostgres() {
  try {
    pgPool = new Pool({
      host: process.env.POSTGRES_HOST || 'localhost',
      port: process.env.POSTGRES_PORT || 5432,
      database: process.env.POSTGRES_DB || 'reptiloid_finance',
      user: process.env.POSTGRES_USER || 'finance_admin',
      password: process.env.POSTGRES_PASSWORD,
      max: 5,
      connectionTimeoutMillis: 5000
    });
    
    await pgPool.query('SELECT 1');
    pgConnected = true;
    logger.info('PostgreSQL connected');
    return true;
  } catch (error) {
    logger.warn('PostgreSQL connection failed, running in standalone mode:', error.message);
    pgConnected = false;
    return false;
  }
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
    
    // Save to database if connected
    if (pgConnected && pgPool) {
      try {
        await pgPool.query(`
          INSERT INTO wallet_config (wallet_type, address, public_key, network, is_active)
          VALUES ('hot', $1, $2, $3, true)
          ON CONFLICT (address) DO UPDATE SET is_active = true, current_seqno = wallet_config.current_seqno
        `, [address, keyPair.publicKey.toString('hex'), process.env.TON_NETWORK]);
      } catch (dbError) {
        logger.warn('Failed to save wallet to DB:', dbError.message);
      }
    }
    
    return hotWallet;
  } catch (error) {
    logger.error('Failed to load hot wallet:', error);
    return null;
  }
}

/**
 * Get wallet balance with rate limiting and retries
 */
async function getWalletBalance(address, retries = 3) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      await waitForRateLimit();
      const addr = Address.parse(address);
      const balance = await tonClient.getBalance(addr);
      consecutiveErrors = 0; // Reset on success
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
 * Get USDT Jetton balance for wallet
 * USDT on TON mainnet: EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs
 */
async function getUSDTBalance(walletAddress, retries = 3) {
  // USDT Jetton Master address on mainnet
  const USDT_MASTER = process.env.TON_NETWORK === 'mainnet' 
    ? 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs'
    : 'kQBqSpvo4S87mX9tjHaG4zhYZeORhVhMapBJpnMZ64jhrP-A'; // testnet USDT
  
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      await waitForRateLimit();
      
      const ownerAddress = Address.parse(walletAddress);
      const jettonMaster = Address.parse(USDT_MASTER);
      
      // Get jetton wallet address for this owner
      const result = await tonClient.runMethod(jettonMaster, 'get_wallet_address', [
        { type: 'slice', cell: beginCell().storeAddress(ownerAddress).endCell() }
      ]);
      
      const jettonWalletAddress = result.stack.readAddress();
      
      // Get balance from jetton wallet
      try {
        const balanceResult = await tonClient.runMethod(jettonWalletAddress, 'get_wallet_data', []);
        const balance = balanceResult.stack.readBigNumber();
        // USDT has 6 decimals
        return Number(balance) / 1000000;
      } catch (e) {
        // Wallet doesn't exist yet = 0 balance
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
        return 0; // Return 0 on error instead of throwing
      }
    }
  }
  return 0;
}

/**
 * Get recent transactions for address with rate limiting
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
  
  consecutiveErrors = 0;
  return { success: true, seqno };
}

// ==================== API ENDPOINTS ====================

/**
 * Health check
 */
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    network: process.env.TON_NETWORK,
    hotWallet: hotWallet ? hotWallet.address : 'not configured',
    pgConnected,
    consecutiveErrors,
    rateLimitBackoff: Math.pow(2, Math.min(consecutiveErrors, 5))
  });
});

/**
 * Generate new wallet (for initial setup)
 */
app.post('/generate-wallet', apiKeyAuth, async (req, res) => {
  try {
    const walletData = await generateWallet();
    
    logger.info(`Generated new wallet: ${walletData.address}`);
    
    // Save to file
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
    
    res.json({
      success: true,
      address: hotWallet.address,
      comment: userId,
      network: process.env.TON_NETWORK,
      message: `Send TON to this address with comment: ${userId}`
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
    
    // Get both TON and USDT balances
    const [tonBalance, usdtBalance] = await Promise.all([
      getWalletBalance(hotWallet.address),
      getUSDTBalance(hotWallet.address)
    ]);
    
    res.json({
      success: true,
      address: hotWallet.address,
      ton_balance: parseFloat(tonBalance),
      usdt_balance: usdtBalance,
      balance: usdtBalance, // backward compatibility
      currency: 'USDT'
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
    
    // Log to DB if connected
    if (pgConnected && pgPool && txId) {
      try {
        await pgPool.query(`
          UPDATE transactions SET status = 'success', updated_at = CURRENT_TIMESTAMP 
          WHERE tx_id = $1
        `, [txId]);
      } catch (dbError) {
        logger.warn('Failed to update transaction in DB:', dbError.message);
      }
    }
    
    logger.info(`Withdrawal sent: ${amount} TON to ${to}`);
    
    res.json({
      success: true,
      to,
      amount,
      seqno: result.seqno
    });
  } catch (error) {
    logger.error('Error sending TON:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get user balance from DB (if connected)
 */
app.get('/user-balance/:userId', apiKeyAuth, async (req, res) => {
  try {
    const { userId } = req.params;
    
    if (!pgConnected || !pgPool) {
      return res.status(503).json({ 
        error: 'Database not connected',
        balance_ton: 0,
        balance_usdt: 0
      });
    }
    
    const result = await pgPool.query(
      'SELECT balance_ton, balance_usdt FROM users_finance WHERE user_id = $1',
      [userId]
    );
    
    if (result.rows.length === 0) {
      return res.json({
        success: true,
        user_id: userId,
        balance_ton: 0,
        balance_usdt: 0
      });
    }
    
    res.json({
      success: true,
      user_id: userId,
      balance_ton: parseFloat(result.rows[0].balance_ton),
      balance_usdt: parseFloat(result.rows[0].balance_usdt)
    });
  } catch (error) {
    logger.error('Error getting user balance:', error);
    res.status(500).json({ error: error.message });
  }
});

// ==================== DEPOSIT LISTENER ====================

let lastProcessedLt = '0';
let isListenerRunning = false;
let depositListenerEnabled = true;

async function processDeposits() {
  if (!hotWallet || isListenerRunning || !depositListenerEnabled) return;
  
  // Skip if too many consecutive errors (backoff)
  if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
    logger.warn(`Skipping deposit check due to ${consecutiveErrors} consecutive errors`);
    return;
  }
  
  isListenerRunning = true;
  
  try {
    const transactions = await getTransactions(hotWallet.address, 20);
    
    for (const tx of transactions) {
      // Skip if already processed
      if (BigInt(tx.lt) <= BigInt(lastProcessedLt)) continue;
      
      // Check if this is an incoming transaction with a comment
      if (tx.inMessage && tx.inMessage.value && parseFloat(tx.inMessage.value) > 0) {
        const comment = tx.inMessage.comment;
        const amount = parseFloat(tx.inMessage.value);
        const fromAddress = tx.inMessage.source;
        
        logger.info(`Incoming deposit: ${amount} TON from ${fromAddress}, comment: ${comment}`);
        
        if (pgConnected && pgPool && comment) {
          try {
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
              logger.warn(`Deposit with unknown comment: ${comment}, amount: ${amount} TON`);
            }
          } catch (dbError) {
            logger.error('Database error processing deposit:', dbError.message);
          }
        }
      }
      
      lastProcessedLt = tx.lt;
    }
  } catch (error) {
    logger.error('Error processing deposits:', error.message);
  } finally {
    isListenerRunning = false;
  }
}

// ==================== STARTUP ====================

async function startServer() {
  try {
    // Initialize TON client (required)
    await initTonClient();
    
    // Load hot wallet (required)
    await initHotWallet();
    
    // Initialize PostgreSQL (optional)
    await initPostgres();
    
    // Start deposit listener with longer interval to avoid rate limits
    if (hotWallet) {
      const pollInterval = parseInt(process.env.DEPOSIT_POLL_INTERVAL) || 30000; // 30 seconds default
      setInterval(processDeposits, pollInterval);
      logger.info(`Deposit listener started with ${pollInterval}ms interval`);
    }
    
    // Start Express server
    const PORT = process.env.PORT || 8002;
    app.listen(PORT, '0.0.0.0', () => {
      logger.info(`TON Service running on port ${PORT}`);
      logger.info(`Network: ${process.env.TON_NETWORK}`);
      logger.info(`Hot wallet: ${hotWallet ? hotWallet.address : 'NOT CONFIGURED'}`);
      logger.info(`PostgreSQL: ${pgConnected ? 'connected' : 'not connected (standalone mode)'}`);
    });
    
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
