import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MessageCircle, Send } from 'lucide-react';

export default function ChatPanel({ trade, messages, newMessage, setNewMessage, sendMsg, messagesEndRef }) {
  return (
    <div className="bg-[#121212] rounded-2xl border border-white/5 flex flex-col h-[500px]">
      <div className="p-4 border-b border-white/5">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <MessageCircle className="w-4 h-4" />
          Сообщения
        </h3>
        <p className="text-[#52525B] text-xs mt-1">Оператор: {trade?.trader_login || 'Загрузка...'}</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="text-center text-[#52525B] text-sm py-8">
            <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
            Начните диалог с оператором
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.sender_type === 'client' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] px-4 py-2 rounded-2xl ${msg.sender_type === 'client'
                ? 'bg-[#7C3AED] text-white rounded-br-sm'
                : 'bg-white/5 text-[#E4E4E7] rounded-bl-sm'
                }`}>
                <p className="text-sm">{msg.content}</p>
                <p className="text-[10px] opacity-50 mt-1">
                  {new Date(msg.created_at).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-white/5">
        <div className="flex gap-2">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMsg()}
            placeholder="Написать сообщение..."
            className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B]"
          />
          <Button onClick={sendMsg} className="bg-[#7C3AED] hover:bg-[#6D28D9]">
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
