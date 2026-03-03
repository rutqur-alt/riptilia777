<?php
/**
 * BITARBITR Invoice API SDK для PHP
 * 
 * Требования: PHP 7.4+, curl extension
 * 
 * Использование:
 *   $client = new BitarbitrClient(
 *       'sk_live_xxx',
 *       'your_secret_key',
 *       'mrc_xxx'
 *   );
 *   
 *   // Создание инвойса
 *   $invoice = $client->createInvoice('ORDER_001', 1500.00, 'https://mysite.com/callback');
 *   
 *   // Проверка статуса
 *   $status = $client->getStatus(null, $invoice['payment_id']);
 *   
 *   // Список транзакций
 *   $transactions = $client->getTransactions('completed', 50);
 */

namespace Bitarbitr;

class BitarbitrException extends \Exception {
    public $code;
    public $httpStatus;
    
    public function __construct($code, $message, $httpStatus = null) {
        $this->code = $code;
        $this->httpStatus = $httpStatus;
        parent::__construct("$code: $message");
    }
}

class RateLimitException extends BitarbitrException {
    public $resetIn;
    
    public function __construct($message, $resetIn = null) {
        parent::__construct('RATE_LIMIT_EXCEEDED', $message, 429);
        $this->resetIn = $resetIn;
    }
}

class AuthenticationException extends BitarbitrException {
    public function __construct($message) {
        parent::__construct('INVALID_API_KEY', $message, 401);
    }
}

class BitarbitrClient {
    const DEFAULT_BASE_URL = 'https://p2p-gateway.preview.emergentagent.com/api/v1/invoice';
    
    private $apiKey;
    private $secretKey;
    private $merchantId;
    private $baseUrl;
    private $timeout;
    
    /**
     * Конструктор клиента
     * 
     * @param string $apiKey API ключ мерчанта
     * @param string $secretKey Secret ключ для подписи
     * @param string $merchantId ID мерчанта в системе
     * @param string $baseUrl Базовый URL API (опционально)
     * @param int $timeout Таймаут запросов в секундах
     */
    public function __construct(
        string $apiKey,
        string $secretKey,
        string $merchantId,
        string $baseUrl = null,
        int $timeout = 30
    ) {
        $this->apiKey = $apiKey;
        $this->secretKey = $secretKey;
        $this->merchantId = $merchantId;
        $this->baseUrl = $baseUrl ?? self::DEFAULT_BASE_URL;
        $this->timeout = $timeout;
    }
    
    /**
     * Генерация HMAC-SHA256 подписи
     */
    private function generateSignature(array $params): string {
        // Убираем sign и null значения
        $signParams = array_filter($params, function($v, $k) {
            return $k !== 'sign' && $v !== null;
        }, ARRAY_FILTER_USE_BOTH);
        
        // Сортируем по ключам
        ksort($signParams);
        
        // Формируем строку
        $signString = http_build_query($signParams) . $this->secretKey;
        
        // HMAC-SHA256
        return hash_hmac('sha256', $signString, $this->secretKey);
    }
    
    /**
     * Выполнение HTTP запроса
     */
    private function request(string $method, string $endpoint, array $data = null, array $query = null): array {
        $url = $this->baseUrl . $endpoint;
        
        if ($query) {
            $url .= '?' . http_build_query($query);
        }
        
        $ch = curl_init();
        
        $headers = [
            'X-Api-Key: ' . $this->apiKey,
            'Content-Type: application/json'
        ];
        
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_HTTPHEADER => $headers
        ]);
        
        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        
        curl_close($ch);
        
        if ($error) {
            throw new BitarbitrException('CURL_ERROR', $error);
        }
        
        $result = json_decode($response, true);
        
        if ($result === null) {
            throw new BitarbitrException('PARSE_ERROR', 'Failed to parse response: ' . $response, $httpCode);
        }
        
        // Обработка ошибок
        if ($httpCode === 429) {
            throw new RateLimitException($result['message'] ?? 'Rate limit exceeded');
        }
        
        if ($httpCode === 401) {
            throw new AuthenticationException($result['message'] ?? 'Invalid API key');
        }
        
        if ($httpCode === 400) {
            $detail = $result['detail'] ?? $result;
            if (is_array($detail)) {
                throw new BitarbitrException($detail['code'] ?? 'ERROR', $detail['message'] ?? json_encode($detail), 400);
            }
            throw new BitarbitrException('BAD_REQUEST', $detail, 400);
        }
        
        if ($httpCode >= 400) {
            throw new BitarbitrException('API_ERROR', json_encode($result), $httpCode);
        }
        
        return $result;
    }
    
    /**
     * Создание инвойса на оплату
     * 
     * @param string $orderId Уникальный ID заказа в вашей системе
     * @param float $amount Сумма в рублях (мин. 100)
     * @param string $callbackUrl URL для callback уведомлений
     * @param string|null $userId ID пользователя (опционально)
     * @param string $currency Валюта (по умолчанию RUB)
     * @param string|null $description Описание платежа (опционально)
     * @return array Invoice данные
     * @throws BitarbitrException
     */
    public function createInvoice(
        string $orderId,
        float $amount,
        string $callbackUrl,
        ?string $userId = null,
        string $currency = 'RUB',
        ?string $description = null
    ): array {
        $params = [
            'merchant_id' => $this->merchantId,
            'order_id' => $orderId,
            'amount' => $amount,
            'currency' => $currency,
            'user_id' => $userId,
            'callback_url' => $callbackUrl,
            'description' => $description
        ];
        
        $params['sign'] = $this->generateSignature($params);
        
        $result = $this->request('POST', '/create', $params);
        
        return [
            'payment_id' => $result['payment_id'],
            'payment_url' => $result['payment_url'],
            'details' => $result['details']
        ];
    }
    
    /**
     * Проверка статуса платежа
     * 
     * @param string|null $orderId ID заказа в вашей системе
     * @param string|null $paymentId ID платежа в нашей системе
     * @return array Статус платежа
     * @throws BitarbitrException
     */
    public function getStatus(?string $orderId = null, ?string $paymentId = null): array {
        if (!$orderId && !$paymentId) {
            throw new \InvalidArgumentException('Требуется order_id или payment_id');
        }
        
        $params = ['merchant_id' => $this->merchantId];
        
        if ($orderId) {
            $params['order_id'] = $orderId;
        }
        if ($paymentId) {
            $params['payment_id'] = $paymentId;
        }
        
        $params['sign'] = $this->generateSignature($params);
        
        $result = $this->request('GET', '/status', null, $params);
        
        return $result['data'];
    }
    
    /**
     * Получение списка транзакций
     * 
     * @param string|null $status Фильтр по статусу (active, completed, dispute)
     * @param int $limit Количество записей (макс. 100)
     * @param int $offset Смещение для пагинации
     * @return array Список транзакций
     * @throws BitarbitrException
     */
    public function getTransactions(?string $status = null, int $limit = 50, int $offset = 0): array {
        $params = ['limit' => $limit, 'offset' => $offset];
        
        if ($status) {
            $params['status'] = $status;
        }
        
        $result = $this->request('GET', '/transactions', null, $params);
        
        return $result['data'];
    }
    
    /**
     * Получение статистики
     * 
     * @param string $period Период (today, week, month, all)
     * @return array Статистика
     * @throws BitarbitrException
     */
    public function getStats(string $period = 'today'): array {
        $result = $this->request('GET', '/stats', null, ['period' => $period]);
        
        return $result['data'];
    }
    
    /**
     * Проверка подписи входящего callback
     * 
     * @param array $payload Данные callback запроса
     * @return bool True если подпись валидна
     */
    public function verifyCallback(array $payload): bool {
        $providedSign = $payload['sign'] ?? '';
        $expectedSign = $this->generateSignature($payload);
        
        return hash_equals(strtolower($expectedSign), strtolower($providedSign));
    }
}

// Пример использования callback обработчика
class CallbackHandler {
    private $client;
    
    public function __construct(BitarbitrClient $client) {
        $this->client = $client;
    }
    
    /**
     * Обработка входящего callback
     * 
     * @param array $payload JSON тело запроса
     * @return array Ответ для отправки
     */
    public function handle(array $payload): array {
        // 1. Проверяем подпись
        if (!$this->client->verifyCallback($payload)) {
            http_response_code(400);
            return ['status' => 'error', 'message' => 'Invalid signature'];
        }
        
        // 2. Обрабатываем по статусу
        $orderId = $payload['order_id'];
        $status = $payload['status'];
        $amount = $payload['amount'];
        
        switch ($status) {
            case 'paid':
                // Успешная оплата - зачисляем средства
                $this->onPaymentSuccess($orderId, $amount);
                break;
                
            case 'failed':
                // Ошибка - уведомляем пользователя
                $this->onPaymentFailed($orderId);
                break;
                
            case 'expired':
                // Истёк срок - отменяем заказ
                $this->onPaymentExpired($orderId);
                break;
        }
        
        // 3. Отвечаем OK
        return ['status' => 'ok'];
    }
    
    protected function onPaymentSuccess(string $orderId, float $amount) {
        // Ваша логика зачисления средств
        // Пример: $this->userService->addBalance($orderId, $amount);
    }
    
    protected function onPaymentFailed(string $orderId) {
        // Ваша логика обработки ошибки
    }
    
    protected function onPaymentExpired(string $orderId) {
        // Ваша логика отмены заказа
    }
}


// ============== ПРИМЕР ИСПОЛЬЗОВАНИЯ ==============

if (php_sapi_name() === 'cli') {
    // Демонстрация при запуске из консоли
    
    $client = new BitarbitrClient(
        'sk_live_50deadc48545483d500e5d30e354510f23c98a1980072302',
        '31e6f7b773d9732a641992717f0f8f0e29593131cc1b0419fb6872ab3616edb7',
        'mrc_20260124_A66181'
    );
    
    echo "=== BITARBITR PHP SDK Demo ===\n\n";
    
    try {
        // Создание инвойса
        echo "Creating invoice...\n";
        $invoice = $client->createInvoice(
            'PHP_SDK_' . date('His'),
            1000.00,
            'https://mysite.com/callback'
        );
        
        echo "Payment ID: {$invoice['payment_id']}\n";
        echo "Payment URL: {$invoice['payment_url']}\n";
        echo "Card: {$invoice['details']['card_number']}\n\n";
        
        // Проверка статуса
        echo "Checking status...\n";
        $status = $client->getStatus(null, $invoice['payment_id']);
        echo "Status: {$status['status']}\n";
        echo "Amount: {$status['amount']} RUB\n\n";
        
        // Статистика
        echo "Getting stats...\n";
        $stats = $client->getStats('today');
        echo "Total invoices: {$stats['summary']['total_invoices']}\n";
        echo "Paid: {$stats['summary']['paid']}\n";
        echo "Volume: {$stats['volume']['total_rub']} RUB\n";
        
    } catch (BitarbitrException $e) {
        echo "Error: {$e->getMessage()}\n";
    }
}
