import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  Webhook, RefreshCw, Trash2, CheckCircle, Clock, 
  XCircle, AlertTriangle, ChevronDown, ChevronUp 
} from 'lucide-react';
import { API } from '@/App';
import axios from 'axios';
import { toast } from 'sonner';

const getStatusIcon = (status) => {
  switch (status) {
    case 'completed': return <CheckCircle className="w-4 h-4 text-green-400" />;
    case 'paid': return <Clock className="w-4 h-4 text-blue-400" />;
    case 'pending': return <Clock className="w-4 h-4 text-yellow-400" />;
    case 'cancelled': return <XCircle className="w-4 h-4 text-zinc-400" />;
    case 'disputed': return <AlertTriangle className="w-4 h-4 text-orange-400" />;
    default: return <Webhook className="w-4 h-4 text-purple-400" />;
  }
};

const getStatusColor = (status) => {
  switch (status) {
    case 'completed': return 'bg-green-500/10 border-green-500/20';
    case 'paid': return 'bg-blue-500/10 border-blue-500/20';
    case 'pending': return 'bg-yellow-500/10 border-yellow-500/20';
    case 'cancelled': return 'bg-zinc-500/10 border-zinc-500/20';
    case 'disputed': return 'bg-orange-500/10 border-orange-500/20';
    default: return 'bg-purple-500/10 border-purple-500/20';
  }
};

const formatTime = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

export default function WebhookPanel({ apiKey, collapsed = false }) {
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(!collapsed);
  const [expandedItems, setExpandedItems] = useState({});

  const loadWebhooks = async () => {
    if (!apiKey) return;
    setLoading(true);
    try {
      const res = await axios.get(`${API}/v1/invoice/test-webhooks`, {
        headers: { 'X-Api-Key': apiKey }
      });
      setWebhooks(res.data.webhooks || []);
    } catch (e) {
      console.error('Error loading webhooks:', e);
    } finally {
      setLoading(false);
    }
  };

  const clearWebhooks = async () => {
    if (!confirm('Очистить все вебхуки?')) return;
    try {
      await axios.delete(`${API}/v1/invoice/test-webhooks`, {
        headers: { 'X-Api-Key': apiKey }
      });
      setWebhooks([]);
      toast.success('Вебхуки очищены');
    } catch (e) {
      toast.error('Ошибка');
    }
  };

  const toggleItem = (id) => {
    setExpandedItems(prev => ({ ...prev, [id]: !prev[id] }));
  };

  useEffect(() => {
    if (apiKey) {
      loadWebhooks();
      // Poll for new webhooks every 3 seconds
      const interval = setInterval(loadWebhooks, 3000);
      return () => clearInterval(interval);
    }
  }, [apiKey]);

  if (!apiKey) return null;

  return (
    <Card className="bg-[#121212] border-white/5">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle 
            className="text-sm flex items-center gap-2 cursor-pointer"
            onClick={() => setExpanded(!expanded)}
          >
            <Webhook className="w-4 h-4 text-purple-400" />
            <span className="text-white">Входящие вебхуки</span>
            {webhooks.length > 0 && (
              <span className="bg-purple-500/20 text-purple-400 text-xs px-2 py-0.5 rounded-full">
                {webhooks.length}
              </span>
            )}
            {expanded ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
          </CardTitle>
          <div className="flex gap-1">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={loadWebhooks}
              disabled={loading}
              className="h-7 w-7 p-0"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-zinc-400 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            {webhooks.length > 0 && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={clearWebhooks}
                className="h-7 w-7 p-0"
              >
                <Trash2 className="w-3.5 h-3.5 text-zinc-400" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      
      {expanded && (
        <CardContent className="pt-2">
          {webhooks.length === 0 ? (
            <div className="text-center py-6 text-zinc-500">
              <Webhook className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">Вебхуки появятся здесь</p>
              <p className="text-xs mt-1">При изменении статуса платежа</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {webhooks.map((wh) => (
                <div 
                  key={wh.id} 
                  className={`rounded-lg border p-3 ${getStatusColor(wh.status)}`}
                >
                  <div 
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => toggleItem(wh.id)}
                  >
                    <div className="flex items-center gap-2">
                      {getStatusIcon(wh.status)}
                      <span className="text-white text-sm font-medium uppercase">
                        {wh.status || 'unknown'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-zinc-400 text-xs">
                        {formatTime(wh.received_at)}
                      </span>
                      {expandedItems[wh.id] ? (
                        <ChevronUp className="w-4 h-4 text-zinc-500" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-zinc-500" />
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-4 mt-2 text-xs text-zinc-400">
                    <span>ID: {wh.payment_id?.slice(0, 20)}...</span>
                    {wh.amount && <span>{Math.round(wh.amount).toLocaleString()} RUB</span>}
                  </div>
                  
                  {expandedItems[wh.id] && (
                    <div className="mt-3 pt-3 border-t border-white/5">
                      <pre className="text-xs text-zinc-300 bg-black/30 rounded p-2 overflow-x-auto">
                        {JSON.stringify(wh.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
