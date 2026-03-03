import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Store, Package, Plus, Trash2, Edit, Eye, EyeOff, Upload, Clock, CheckCircle, XCircle, AlertCircle, Download, Send, MessageCircle, Infinity, Image, FileText, Camera } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { toast } from "sonner";

// Category mapping
const CATEGORIES = {
  accounts: "Аккаунты",
  software: "Софт",
  databases: "Базы данных",
  tools: "Инструменты",
  guides: "Гайды и схемы",
  keys: "Ключи",
  financial: "Финансовое",
  templates: "Шаблоны",
  other: "Другое"
};

const getCategoryLabel = (category) => CATEGORIES[category] || category;

// Shop Application Chat - uses unified_conversations for proper routing
function ShopApplicationChat({ onSuccess }) {
  const { token, user } = useAuth();
  const [application, setApplication] = useState(null);
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    shop_name: "",
    shop_description: "",
    categories: [],
    telegram: "",
    experience: ""
  });
  const messagesEndRef = useRef(null);

  useEffect(() => {
    checkExistingApplication();
    const interval = setInterval(fetchMessages, 5000);
    return () => clearInterval(interval);
  }, [token]);

  const checkExistingApplication = async () => {
    try {
      const response = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data?.application) {
        setApplication(response.data.application);
        // Fetch conversation
        await fetchConversation(response.data.application.id);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchConversation = async (applicationId) => {
    try {
      const response = await axios.get(`${API}/msg/user/conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const conv = response.data.find(c => c.type === "shop_application" && c.related_id === applicationId);
      if (conv) {
        setConversation(conv);
        await fetchMessages(conv.id);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const fetchMessages = async (convId) => {
    const id = convId || conversation?.id;
    if (!id) return;
    try {
      const response = await axios.get(`${API}/msg/user/conversations/${id}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data || []);
      
      // Check if shop was approved
      const appRes = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (appRes.data?.has_shop) {
        onSuccess?.();
      }
    } catch (error) {
      console.error(error);
    }
  };

  const createApplication = async () => {
    if (!formData.shop_name || !formData.shop_description || formData.categories.length === 0) {
      toast.error("Заполните все обязательные поля");
      return;
    }
    try {
      const response = await axios.post(`${API}/shop/apply`, formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Заявка создана!");
      setShowForm(false);
      await checkExistingApplication();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания заявки");
    }
  };

  const handleSend = async () => {
    if (!newMessage.trim() || !conversation) return;
    setSending(true);
    try {
      await axios.post(`${API}/msg/user/conversations/${conversation.id}/messages`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage("");
      await fetchMessages();
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  const toggleCategory = (cat) => {
    setFormData(prev => ({
      ...prev,
      categories: prev.categories.includes(cat)
        ? prev.categories.filter(c => c !== cat)
        : [...prev.categories, cat]
    }));
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // No application yet - show form or start button
  if (!application) {
    if (!showForm) {
      return (
        <div className="max-w-2xl mx-auto text-center py-12">
          <div className="w-20 h-20 bg-gradient-to-br from-[#10B981]/20 to-[#34D399]/10 rounded-3xl flex items-center justify-center mx-auto mb-6">
            <Store className="w-10 h-10 text-[#10B981]" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">Открыть магазин</h2>
          <p className="text-[#71717A] mb-6 max-w-md mx-auto">
            Чтобы открыть магазин на маркетплейсе, заполните заявку. 
            Администратор рассмотрит её и свяжется с вами.
          </p>
          <Button onClick={() => setShowForm(true)} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-12 px-8">
            <MessageCircle className="w-5 h-5 mr-2" />
            Подать заявку
          </Button>
        </div>
      );
    }

    // Application form
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h2 className="text-xl font-bold text-white mb-6">Заявка на открытие магазина</h2>
          
          <div className="space-y-4">
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Название магазина *</label>
              <Input
                value={formData.shop_name}
                onChange={(e) => setFormData({...formData, shop_name: e.target.value})}
                placeholder="Мой магазин"
                className="bg-[#0A0A0A] border-white/10 text-white"
              />
            </div>
            
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Категории товаров *</label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(CATEGORIES).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => toggleCategory(key)}
                    className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                      formData.categories.includes(key)
                        ? "bg-[#10B981] text-white"
                        : "bg-[#1A1A1A] text-[#71717A] hover:bg-white/10"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Описание магазина *</label>
              <Textarea
                value={formData.shop_description}
                onChange={(e) => setFormData({...formData, shop_description: e.target.value})}
                placeholder="Расскажите о товарах, которые планируете продавать..."
                className="bg-[#0A0A0A] border-white/10 text-white min-h-[100px]"
              />
            </div>
            
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Telegram для связи</label>
              <Input
                value={formData.telegram}
                onChange={(e) => setFormData({...formData, telegram: e.target.value})}
                placeholder="@username"
                className="bg-[#0A0A0A] border-white/10 text-white"
              />
            </div>
            
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Опыт в продажах</label>
              <Textarea
                value={formData.experience}
                onChange={(e) => setFormData({...formData, experience: e.target.value})}
                placeholder="Опишите ваш опыт (необязательно)"
                className="bg-[#0A0A0A] border-white/10 text-white"
              />
            </div>
          </div>
          
          <div className="flex gap-3 mt-6">
            <Button onClick={() => setShowForm(false)} variant="outline" className="flex-1 border-white/10 text-white">
              Отмена
            </Button>
            <Button onClick={createApplication} className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white">
              Отправить заявку
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Check if rejected
  if (application.status === "rejected") {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-2xl p-6 text-center">
          <XCircle className="w-12 h-12 text-[#EF4444] mx-auto mb-4" />
          <h3 className="text-xl font-bold text-white mb-2">Заявка отклонена</h3>
          <p className="text-[#A1A1AA] mb-4">{application.admin_comment || "Администратор отклонил вашу заявку"}</p>
          <Button onClick={() => { setApplication(null); setShowForm(true); }} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl">
            Подать новую заявку
          </Button>
        </div>
      </div>
    );
  }

  const statusColors = {
    pending: "bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30",
    reviewing: "bg-[#3B82F6]/10 text-[#3B82F6] border-[#3B82F6]/30",
    approved: "bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30"
  };

  const statusNames = {
    pending: "На рассмотрении",
    reviewing: "В обработке",
    approved: "Одобрено"
  };

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-4 mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#10B981]/10 rounded-xl flex items-center justify-center">
            <Store className="w-5 h-5 text-[#10B981]" />
          </div>
          <div>
            <div className="text-white font-medium">{application.shop_name}</div>
            <div className="text-xs text-[#52525B]">Заявка на открытие магазина</div>
          </div>
        </div>
        <span className={`px-3 py-1.5 rounded-lg text-xs border ${statusColors[application.status] || statusColors.pending}`}>
          {statusNames[application.status] || "На рассмотрении"}
        </span>
      </div>

      {/* Chat */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden flex flex-col" style={{ height: "500px" }}>
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.sender_id === user?.id ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] p-3 rounded-2xl ${
                msg.sender_id === user?.id
                  ? "bg-[#10B981] text-white"
                  : msg.sender_role === "system" || msg.is_system
                  ? "bg-[#7C3AED]/20 text-[#A78BFA] border border-[#7C3AED]/30"
                  : "bg-[#1A1A1A] text-white"
              }`}>
                {msg.sender_role && msg.sender_role !== "system" && msg.sender_id !== user?.id && (
                  <div className="text-xs text-[#10B981] mb-1 font-medium">{msg.sender_nickname || "Модератор"}</div>
                )}
                <p className="whitespace-pre-wrap">{msg.content}</p>
                <div className={`text-xs mt-1 ${msg.sender_id === user?.id ? "text-white/70" : "text-[#52525B]"}`}>
                  {new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-white/5 p-4">
          <div className="flex gap-2">
            <Input
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="Написать сообщение..."
              className="flex-1 bg-[#0A0A0A] border-white/10 text-white"
              disabled={sending}
            />
            <Button onClick={handleSend} disabled={sending || !newMessage.trim()} className="bg-[#10B981] hover:bg-[#059669] text-white">
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Application Status View - now just a wrapper that redirects to chat
function ApplicationStatus({ application, onRefresh }) {
  // Redirect to chat
  return <ShopApplicationChat onSuccess={onRefresh} />;
}

// Shop Management Panel
function ShopManagement() {
  const { token, user } = useAuth();
  const [products, setProducts] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [addingStock, setAddingStock] = useState(null);
  const [viewingStock, setViewingStock] = useState(null);
  const [activeTab, setActiveTab] = useState("products");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [dashboardRes, productsRes] = await Promise.all([
        axios.get(`${API}/shop/dashboard`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/shop/products`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setDashboard(dashboardRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      console.error("Failed to fetch shop data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteProduct = async (productId) => {
    if (!confirm("Удалить товар?")) return;
    
    try {
      await axios.delete(`${API}/shop/products/${productId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Товар удалён");
      fetchData();
    } catch (error) {
      toast.error("Ошибка удаления");
    }
  };

  const handleToggleActive = async (product) => {
    try {
      await axios.put(
        `${API}/shop/products/${product.id}`,
        { is_active: !product.is_active },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(product.is_active ? "Товар скрыт" : "Товар активирован");
      fetchData();
    } catch (error) {
      toast.error("Ошибка обновления");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      {/* Shop Dashboard Header */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 mb-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-xl bg-[#10B981]/10 flex items-center justify-center overflow-hidden">
              {dashboard?.shop?.logo ? (
                <img src={dashboard.shop.logo} alt="" className="w-full h-full object-cover" />
              ) : (
                <Store className="w-8 h-8 text-[#10B981]" />
              )}
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{dashboard?.shop?.name}</h2>
              <p className="text-[#71717A] text-sm">{dashboard?.shop?.description || "Ваш магазин"}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-[#10B981] font-mono">
              {dashboard?.shop?.shop_balance?.toFixed(2) || "0.00"} <span className="text-lg text-[#71717A]">USDT</span>
            </div>
            <div className="text-[#71717A] text-sm">Торговый баланс</div>
          </div>
        </div>

        <div className="border-t border-white/5 pt-4 mb-4">
          <div className="text-[#71717A] text-sm mb-2">
            Комиссия вашего магазина: <span className="text-[#F59E0B] font-semibold">{dashboard?.shop?.commission_rate || 5}%</span>
            <span className="text-[#52525B]"> (устанавливается администратором)</span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-[#52525B] text-xs mb-1">Сегодня</div>
            <div className="text-white font-bold text-lg">+{dashboard?.stats?.today?.revenue?.toFixed(2) || "0.00"} USDT</div>
            <div className="text-[#71717A] text-xs">{dashboard?.stats?.today?.orders || 0} заказов</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-[#52525B] text-xs mb-1">Неделя</div>
            <div className="text-white font-bold text-lg">+{dashboard?.stats?.week?.revenue?.toFixed(2) || "0.00"} USDT</div>
            <div className="text-[#71717A] text-xs">{dashboard?.stats?.week?.orders || 0} заказов</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-[#52525B] text-xs mb-1">Месяц</div>
            <div className="text-white font-bold text-lg">+{dashboard?.stats?.month?.revenue?.toFixed(2) || "0.00"} USDT</div>
            <div className="text-[#71717A] text-xs">{dashboard?.stats?.month?.orders || 0} заказов</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        {[
          { key: "products", label: "Товары" },
          { key: "orders", label: "Заказы" },
          { key: "messages", label: "Сообщения" },
          { key: "finances", label: "Финансы" },
          { key: "settings", label: "Настройки" }
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-[#10B981]/15 text-[#10B981]"
                : "text-[#71717A] hover:text-white hover:bg-white/5"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "products" && (
        <>
          {/* Products Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="text-[#71717A] text-sm">
              Товаров: {products.length} | В наличии: {dashboard?.inventory?.total_stock || 0} шт.
            </div>
            <Button
              onClick={() => setShowAddProduct(true)}
              className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl gap-2"
            >
              <Plus className="w-4 h-4" />
              Добавить товар
            </Button>
          </div>

      {/* Products List */}
      {products.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-12 text-center">
          <Package className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A] mb-4">У вас пока нет товаров</p>
          <Button
            onClick={() => setShowAddProduct(true)}
            className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl"
          >
            Добавить первый товар
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {products.map(product => (
            <div key={product.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center gap-4">
                {/* Image */}
                <div className="w-16 h-16 rounded-lg bg-[#1A1A1A] flex items-center justify-center overflow-hidden flex-shrink-0">
                  {product.image_url ? (
                    <img src={product.image_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <Package className="w-6 h-6 text-[#52525B]" />
                  )}
                </div>
                
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-white font-medium truncate">{product.name}</h4>
                    {!product.is_active && (
                      <span className="text-xs bg-[#52525B]/20 text-[#71717A] px-2 py-0.5 rounded">Скрыт</span>
                    )}
                  </div>
                  <p className="text-[#71717A] text-sm truncate">{product.description}</p>
                  <div className="flex items-center gap-4 mt-1">
                    <span className="text-[#10B981] font-semibold">{product.price} {product.currency}</span>
                    <span className="text-[#52525B] text-sm">В наличии: {product.is_infinite ? "∞" : (product.stock_count || 0)}</span>
                    <span className="text-[#52525B] text-xs">{getCategoryLabel(product.category)}</span>
                  </div>
                </div>
                
                {/* Actions */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setViewingStock(product)}
                    className="text-[#7C3AED] hover:text-[#A78BFA] hover:bg-[#7C3AED]/10"
                    title="Просмотр наличия"
                  >
                    <Package className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setAddingStock(product)}
                    className="text-[#A1A1AA] hover:text-white hover:bg-white/5"
                    title="Добавить товар"
                  >
                    <Upload className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleToggleActive(product)}
                    className="text-[#A1A1AA] hover:text-white hover:bg-white/5"
                    title={product.is_active ? "Скрыть" : "Показать"}
                  >
                    {product.is_active ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setEditingProduct(product)}
                    className="text-[#A1A1AA] hover:text-white hover:bg-white/5"
                  >
                    <Edit className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDeleteProduct(product.id)}
                    className="text-[#EF4444] hover:text-[#EF4444] hover:bg-[#EF4444]/10"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      </>
      )}

      {activeTab === "orders" && (
        <ShopOrdersTab token={token} />
      )}

      {activeTab === "finances" && (
        <ShopFinancesTab token={token} shopBalance={dashboard?.shop?.shop_balance} />
      )}

      {activeTab === "messages" && (
        <ShopMessagesTab token={token} shopName={dashboard?.shop?.name} />
      )}

      {activeTab === "settings" && (
        <ShopSettingsTab token={token} shop={dashboard?.shop} onUpdate={fetchData} />
      )}

      {/* Add Product Modal */}
      {showAddProduct && (
        <ProductFormModal
          onClose={() => setShowAddProduct(false)}
          onSuccess={() => { setShowAddProduct(false); fetchData(); }}
        />
      )}

      {/* Edit Product Modal */}
      {editingProduct && (
        <ProductFormModal
          product={editingProduct}
          onClose={() => setEditingProduct(null)}
          onSuccess={() => { setEditingProduct(null); fetchData(); }}
        />
      )}

      {/* Add Stock Modal */}
      {addingStock && (
        <AddStockModal
          product={addingStock}
          onClose={() => setAddingStock(null)}
          onSuccess={() => { setAddingStock(null); fetchData(); }}
        />
      )}

      {/* View/Edit Stock Modal */}
      {viewingStock && (
        <ViewStockModal
          product={viewingStock}
          onClose={() => setViewingStock(null)}
          onUpdate={() => { fetchData(); }}
        />
      )}
    </div>
  );
}

// Product Form Modal
function ProductFormModal({ product, onClose, onSuccess }) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const imageInputRef = useRef(null);
  const fileInputRef = useRef(null);
  
  const [formData, setFormData] = useState({
    name: product?.name || "",
    description: product?.description || "",
    price: product?.price || "",
    category: product?.category || "",
    image_url: product?.image_url || "",
    is_infinite: product?.is_infinite || false,
    attached_files: product?.attached_files || []
  });
  const [priceVariants, setPriceVariants] = useState(product?.price_variants || []);
  const [showVariants, setShowVariants] = useState((product?.price_variants?.length || 0) > 0);

  // Upload image
  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Check file size - 2MB for photos
    const maxSize = 2 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error("Фото слишком большое. Максимум 2MB");
      return;
    }
    
    setUploadingImage(true);
    try {
      const formDataUpload = new FormData();
      formDataUpload.append("file", file);
      
      const response = await axios.post(`${API}/shop/upload`, formDataUpload, {
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      
      setFormData({ ...formData, image_url: response.data.url });
      toast.success("Изображение загружено");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка загрузки");
    } finally {
      setUploadingImage(false);
    }
  };

  // Upload attached file
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Check file size - 1MB for files
    const maxSize = 1 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error("Файл слишком большой. Максимум 1MB");
      return;
    }
    
    setUploadingFile(true);
    try {
      const formDataUpload = new FormData();
      formDataUpload.append("file", file);
      
      const response = await axios.post(`${API}/shop/upload`, formDataUpload, {
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      
      setFormData({ 
        ...formData, 
        attached_files: [...formData.attached_files, response.data.url] 
      });
      toast.success("Файл прикреплён");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка загрузки");
    } finally {
      setUploadingFile(false);
    }
  };

  const removeAttachedFile = (index) => {
    setFormData({
      ...formData,
      attached_files: formData.attached_files.filter((_, i) => i !== index)
    });
  };

  const addPriceVariant = () => {
    setPriceVariants([...priceVariants, { quantity: 2, price: "" }]);
  };

  const removePriceVariant = (index) => {
    setPriceVariants(priceVariants.filter((_, i) => i !== index));
  };

  const updateVariant = (index, field, value) => {
    const updated = [...priceVariants];
    updated[index][field] = field === "quantity" ? parseInt(value) || 1 : value;
    setPriceVariants(updated);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = {
        ...formData,
        price: parseFloat(formData.price),
        currency: "USDT",
        price_variants: showVariants ? priceVariants.map(v => ({
          quantity: v.quantity,
          price: parseFloat(v.price),
          label: v.label || `${v.quantity} шт.`
        })) : []
      };

      if (product) {
        await axios.put(
          `${API}/shop/products/${product.id}`,
          payload,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success("Товар обновлён");
      } else {
        await axios.post(
          `${API}/shop/products`,
          payload,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success("Товар создан");
      }
      onSuccess();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка сохранения");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-lg my-8">
        <h3 className="text-lg font-semibold text-white mb-4">
          {product ? "Редактировать товар" : "Новый товар"}
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Product Image */}
          <div>
            <label className="block text-sm text-[#A1A1AA] mb-2">Фото товара</label>
            <div className="flex items-start gap-4">
              <div 
                onClick={() => imageInputRef.current?.click()}
                className="w-24 h-24 bg-[#1A1A1A] border border-dashed border-white/20 rounded-xl flex items-center justify-center cursor-pointer hover:border-[#7C3AED] transition-colors overflow-hidden"
              >
                {formData.image_url ? (
                  <img src={formData.image_url} alt="" className="w-full h-full object-cover" />
                ) : uploadingImage ? (
                  <div className="animate-spin w-6 h-6 border-2 border-[#7C3AED] border-t-transparent rounded-full" />
                ) : (
                  <Camera className="w-8 h-8 text-[#52525B]" />
                )}
              </div>
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
              />
              <div className="flex-1">
                <p className="text-xs text-[#71717A] mb-2">
                  Нажмите чтобы загрузить фото товара. JPG, PNG, WebP до 5MB
                </p>
                {formData.image_url && (
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, image_url: "" })}
                    className="text-xs text-[#EF4444] hover:text-[#F87171]"
                  >
                    Удалить фото
                  </button>
                )}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm text-[#A1A1AA] mb-1">Название *</label>
            <Input
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Название товара"
              className="bg-[#0A0A0A] border-white/10 text-white rounded-xl"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm text-[#A1A1AA] mb-1">Описание *</label>
            <Textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Подробное описание товара..."
              rows={4}
              className="bg-[#0A0A0A] border-white/10 text-white rounded-xl resize-none"
              required
            />
          </div>

          {/* Attached Files */}
          <div>
            <label className="block text-sm text-[#A1A1AA] mb-2">Прикреплённые файлы</label>
            <div className="space-y-2">
              {formData.attached_files.map((file, index) => (
                <div key={index} className="flex items-center gap-2 bg-[#1A1A1A] rounded-lg px-3 py-2">
                  <FileText className="w-4 h-4 text-[#7C3AED]" />
                  <span className="text-sm text-white flex-1 truncate">{file.split('/').pop()}</span>
                  <button
                    type="button"
                    onClick={() => removeAttachedFile(index)}
                    className="text-[#EF4444] hover:text-[#F87171]"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingFile}
                className="flex items-center gap-2 text-sm text-[#7C3AED] hover:text-[#A78BFA]"
              >
                {uploadingFile ? (
                  <div className="animate-spin w-4 h-4 border-2 border-[#7C3AED] border-t-transparent rounded-full" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                Прикрепить файл или документ
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,.pdf,.txt"
                onChange={handleFileUpload}
                className="hidden"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-[#A1A1AA] mb-1">Цена (USDT) *</label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={formData.price}
                onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                placeholder="10.00"
                className="bg-[#0A0A0A] border-white/10 text-white rounded-xl"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-[#A1A1AA] mb-1">Категория *</label>
              <select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl"
                required
              >
                <option value="">Выберите категорию</option>
                <option value="accounts">Аккаунты</option>
                <option value="software">Софт</option>
                <option value="databases">Базы данных</option>
                <option value="tools">Инструменты</option>
                <option value="guides">Гайды и схемы</option>
                <option value="keys">Ключи</option>
                <option value="financial">Финансовое</option>
                <option value="templates">Шаблоны</option>
                <option value="other">Другое</option>
              </select>
            </div>
          </div>

          {/* Infinite Product Toggle */}
          <div className="bg-[#1A1A1A] border border-white/5 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${formData.is_infinite ? 'bg-[#7C3AED]/20 text-[#A78BFA]' : 'bg-[#27272A] text-[#52525B]'}`}>
                  <Infinity className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-sm text-white font-medium">Бесконечный товар</div>
                  <div className="text-xs text-[#71717A]">Цифровой товар, который не заканчивается</div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFormData({ ...formData, is_infinite: !formData.is_infinite })}
                className={`w-12 h-6 rounded-full transition-colors ${formData.is_infinite ? 'bg-[#7C3AED]' : 'bg-[#27272A]'}`}
              >
                <div className={`w-5 h-5 bg-white rounded-full transition-transform ${formData.is_infinite ? 'translate-x-6' : 'translate-x-0.5'}`} />
              </button>
            </div>
          </div>

          {/* Price Variants */}
          <div className="border-t border-white/5 pt-4">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm text-[#A1A1AA]">Варианты цен (опт/скидки)</label>
              <button
                type="button"
                onClick={() => setShowVariants(!showVariants)}
                className="text-xs text-[#7C3AED] hover:text-[#A78BFA]"
              >
                {showVariants ? "Скрыть" : "Добавить"}
              </button>
            </div>
            
            {showVariants && (
              <div className="space-y-2">
                {priceVariants.map((variant, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <Input
                      type="number"
                      min="1"
                      value={variant.quantity}
                      onChange={(e) => updateVariant(index, "quantity", e.target.value)}
                      placeholder="Кол-во"
                      className="w-20 bg-[#0A0A0A] border-white/10 text-white rounded-lg text-sm"
                    />
                    <span className="text-[#52525B]">шт. =</span>
                    <Input
                      type="number"
                      step="0.01"
                      value={variant.price}
                      onChange={(e) => updateVariant(index, "price", e.target.value)}
                      placeholder="Цена"
                      className="w-24 bg-[#0A0A0A] border-white/10 text-white rounded-lg text-sm"
                    />
                    <span className="text-[#52525B]">USDT</span>
                    <button
                      type="button"
                      onClick={() => removePriceVariant(index)}
                      className="text-[#EF4444] hover:text-[#F87171] p-1"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addPriceVariant}
                  className="text-xs text-[#10B981] hover:text-[#34D399] flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" /> Добавить вариант
                </button>
                <p className="text-[#52525B] text-xs">
                  Пример: 2 шт. = 45 USDT (скидка 10%), 5 шт. = 100 USDT (опт)
                </p>
              </div>
            )}
          </div>
          
          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="flex-1 bg-transparent border-white/10 text-white rounded-xl"
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl"
            >
              {loading ? "Сохранение..." : "Сохранить"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Add Stock Modal
function AddStockModal({ product, onClose, onSuccess }) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("single"); // single or bulk
  const [stockItems, setStockItems] = useState([{ text: "", file_url: null, photo_url: null }]);
  const [bulkContent, setBulkContent] = useState("");
  const [uploadingPhoto, setUploadingPhoto] = useState(null);
  const [uploadingFile, setUploadingFile] = useState(null);
  const photoInputRef = useRef(null);
  const fileInputRef = useRef(null);

  const handlePhotoUpload = async (e, index) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Check file size - 2MB for photos
    const maxSize = 2 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error("Фото слишком большое. Максимум 2MB");
      return;
    }
    
    setUploadingPhoto(index);
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await axios.post(`${API}/shop/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      
      const updated = [...stockItems];
      updated[index].photo_url = response.data.url;
      setStockItems(updated);
      toast.success("Фото загружено");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка загрузки фото");
    } finally {
      setUploadingPhoto(null);
    }
  };

  const handleFileUpload = async (e, index) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Check file size - 1MB for documents
    const maxSize = 1 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error("Файл слишком большой. Максимум 1MB");
      return;
    }
    
    setUploadingFile(index);
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await axios.post(`${API}/shop/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      
      const updated = [...stockItems];
      updated[index].file_url = response.data.url;
      setStockItems(updated);
      toast.success("Файл прикреплён");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка загрузки файла");
    } finally {
      setUploadingFile(null);
    }
  };

  const addStockItem = () => {
    setStockItems([...stockItems, { text: "", file_url: null, photo_url: null }]);
  };

  const removeStockItem = (index) => {
    if (stockItems.length === 1) return;
    setStockItems(stockItems.filter((_, i) => i !== index));
  };

  const updateStockItem = (index, field, value) => {
    const updated = [...stockItems];
    updated[index][field] = value;
    setStockItems(updated);
  };

  const handleDownloadStock = async () => {
    try {
      const response = await axios.get(
        `${API}/shop/products/${product.id}/download-stock`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      const blob = new Blob([response.data.content], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${product.name.replace(/[^a-zA-Z0-9]/g, '_')}_stock.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.success(`Скачано ${response.data.count} шт.`);
    } catch (error) {
      toast.error("Ошибка скачивания");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (mode === "bulk") {
        // Bulk upload - text only
        const items = bulkContent.split("\n").map(s => s.trim()).filter(s => s);
        if (items.length === 0) {
          toast.error("Добавьте хотя бы один элемент");
          setLoading(false);
          return;
        }

        await axios.post(
          `${API}/shop/products/${product.id}/stock/bulk`,
          items.map(text => ({ text })),
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(`Добавлено ${items.length} шт.`);
      } else {
        // Single items with files
        const validItems = stockItems.filter(item => item.text || item.file_url || item.photo_url);
        if (validItems.length === 0) {
          toast.error("Добавьте хотя бы один элемент");
          setLoading(false);
          return;
        }

        await axios.post(
          `${API}/shop/products/${product.id}/stock/bulk`,
          validItems,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(`Добавлено ${validItems.length} шт.`);
      }
      
      onSuccess();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка добавления");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-lg my-8">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-white">Добавить наличие</h3>
          {product.stock_count > 0 && (
            <button
              type="button"
              onClick={handleDownloadStock}
              className="text-xs text-[#7C3AED] hover:text-[#A78BFA] flex items-center gap-1"
            >
              <Download className="w-3 h-3" />
              Скачать остатки ({product.stock_count})
            </button>
          )}
        </div>
        <p className="text-[#71717A] text-sm mb-4">{product.name}</p>

        {/* Mode Tabs */}
        <div className="flex gap-2 mb-4">
          <button
            type="button"
            onClick={() => setMode("single")}
            className={`px-4 py-2 rounded-lg text-sm ${
              mode === "single" ? "bg-[#10B981] text-white" : "bg-[#1A1A1A] text-[#71717A]"
            }`}
          >
            По одному
          </button>
          <button
            type="button"
            onClick={() => setMode("bulk")}
            className={`px-4 py-2 rounded-lg text-sm ${
              mode === "bulk" ? "bg-[#10B981] text-white" : "bg-[#1A1A1A] text-[#71717A]"
            }`}
          >
            Массовая загрузка
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "bulk" ? (
            <div>
              <label className="block text-sm text-[#A1A1AA] mb-1">
                Текстовый контент (каждая строка = 1 единица)
              </label>
              <Textarea
                value={bulkContent}
                onChange={(e) => setBulkContent(e.target.value)}
                placeholder={"Ключ1\nКлюч2\nlogin:password\n..."}
                rows={8}
                className="bg-[#0A0A0A] border-white/10 text-white rounded-xl resize-none font-mono text-sm"
              />
            </div>
          ) : (
            <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
              {stockItems.map((item, index) => (
                <div key={index} className="bg-[#1A1A1A] rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#71717A]">Единица #{index + 1}</span>
                    {stockItems.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeStockItem(index)}
                        className="text-[#EF4444] hover:text-[#F87171]"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                  
                  {/* Text */}
                  <Textarea
                    value={item.text}
                    onChange={(e) => updateStockItem(index, "text", e.target.value)}
                    placeholder="Текст (данные, ключ, логин:пароль...)"
                    rows={2}
                    className="bg-[#0A0A0A] border-white/10 text-white rounded-lg resize-none font-mono text-sm"
                  />
                  
                  {/* Photo & File */}
                  <div className="flex gap-2">
                    {/* Photo */}
                    <div className="flex-1">
                      {item.photo_url ? (
                        <div className="relative">
                          <img src={item.photo_url} alt="" className="w-full h-20 object-cover rounded-lg" />
                          <button
                            type="button"
                            onClick={() => updateStockItem(index, "photo_url", null)}
                            className="absolute top-1 right-1 bg-black/50 p-1 rounded"
                          >
                            <XCircle className="w-4 h-4 text-white" />
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            photoInputRef.current.dataset.index = index;
                            photoInputRef.current.click();
                          }}
                          disabled={uploadingPhoto === index}
                          className="w-full h-20 border border-dashed border-white/20 rounded-lg flex flex-col items-center justify-center gap-1 text-[#52525B] hover:border-[#10B981] hover:text-[#10B981] transition-colors"
                        >
                          {uploadingPhoto === index ? (
                            <div className="w-5 h-5 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <>
                              <Camera className="w-5 h-5" />
                              <span className="text-xs">Фото</span>
                            </>
                          )}
                        </button>
                      )}
                    </div>
                    
                    {/* File */}
                    <div className="flex-1">
                      {item.file_url ? (
                        <div className="relative h-20 bg-[#0A0A0A] rounded-lg flex items-center justify-center">
                          <FileText className="w-6 h-6 text-[#7C3AED]" />
                          <button
                            type="button"
                            onClick={() => updateStockItem(index, "file_url", null)}
                            className="absolute top-1 right-1 bg-black/50 p-1 rounded"
                          >
                            <XCircle className="w-4 h-4 text-white" />
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            fileInputRef.current.dataset.index = index;
                            fileInputRef.current.click();
                          }}
                          disabled={uploadingFile === index}
                          className="w-full h-20 border border-dashed border-white/20 rounded-lg flex flex-col items-center justify-center gap-1 text-[#52525B] hover:border-[#7C3AED] hover:text-[#7C3AED] transition-colors"
                        >
                          {uploadingFile === index ? (
                            <div className="w-5 h-5 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <>
                              <FileText className="w-5 h-5" />
                              <span className="text-xs">Файл</span>
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              <button
                type="button"
                onClick={addStockItem}
                className="w-full py-3 border border-dashed border-white/20 rounded-xl text-[#10B981] hover:bg-[#10B981]/10 flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Добавить ещё единицу
              </button>
            </div>
          )}
          
          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="flex-1 bg-transparent border-white/10 text-white rounded-xl"
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl"
            >
              {loading ? "Добавление..." : "Добавить"}
            </Button>
          </div>
        </form>

        {/* Hidden inputs for file upload */}
        <input
          ref={photoInputRef}
          type="file"
          accept="image/*"
          onChange={(e) => handlePhotoUpload(e, parseInt(e.target.dataset.index))}
          className="hidden"
        />
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.pdf,.txt"
          onChange={(e) => handleFileUpload(e, parseInt(e.target.dataset.index))}
          className="hidden"
        />
      </div>
    </div>
  );
}

// View/Edit Stock Modal
function ViewStockModal({ product, onClose, onUpdate }) {
  const { token } = useAuth();
  const [stockItems, setStockItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingItem, setEditingItem] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [saving, setSaving] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const photoInputRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchStock();
  }, []);

  const fetchStock = async () => {
    try {
      const response = await axios.get(
        `${API}/shop/products/${product.id}/stock`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setStockItems(response.data.items || []);
    } catch (error) {
      toast.error("Ошибка загрузки наличия");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (itemId) => {
    setDeleting(itemId);
    try {
      await axios.delete(
        `${API}/shop/products/${product.id}/stock/${itemId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setStockItems(stockItems.filter(item => item.id !== itemId));
      toast.success("Удалено");
      onUpdate();
    } catch (error) {
      toast.error("Ошибка удаления");
    } finally {
      setDeleting(null);
    }
  };

  const handlePhotoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !editingItem) return;
    
    setUploadingPhoto(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await axios.post(`${API}/shop/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      
      setEditingItem({ ...editingItem, photo_url: response.data.url });
      toast.success("Фото загружено");
    } catch (error) {
      toast.error("Ошибка загрузки фото");
    } finally {
      setUploadingPhoto(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !editingItem) return;
    
    setUploadingFile(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await axios.post(`${API}/shop/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      
      setEditingItem({ ...editingItem, file_url: response.data.url });
      toast.success("Файл загружен");
    } catch (error) {
      toast.error("Ошибка загрузки файла");
    } finally {
      setUploadingFile(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingItem) return;
    
    setSaving(true);
    try {
      await axios.put(
        `${API}/shop/products/${product.id}/stock/${editingItem.id}`,
        {
          text: editingItem.text,
          file_url: editingItem.file_url,
          photo_url: editingItem.photo_url
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      toast.success("Сохранено");
      setEditingItem(null);
      fetchStock();
      onUpdate();
    } catch (error) {
      toast.error("Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-2xl my-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white">Наличие товара</h3>
            <p className="text-[#71717A] text-sm">{product.name}</p>
          </div>
          <button
            onClick={onClose}
            className="text-[#71717A] hover:text-white"
          >
            <XCircle className="w-6 h-6" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : stockItems.length === 0 ? (
          <div className="text-center py-12">
            <Package className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
            <p className="text-[#71717A]">Нет наличия</p>
            <p className="text-[#52525B] text-sm">Добавьте товар через кнопку загрузки</p>
          </div>
        ) : (
          <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
            {stockItems.map((item, index) => (
              <div key={item.id || index} className="bg-[#1A1A1A] rounded-xl p-4">
                {editingItem?.id === item.id ? (
                  // Edit mode
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[#10B981]">Редактирование</span>
                      <button
                        onClick={() => setEditingItem(null)}
                        className="text-[#71717A] hover:text-white text-xs"
                      >
                        Отмена
                      </button>
                    </div>
                    
                    <Textarea
                      value={editingItem.text || ""}
                      onChange={(e) => setEditingItem({ ...editingItem, text: e.target.value })}
                      placeholder="Текст (данные, ключ, логин:пароль...)"
                      rows={3}
                      className="bg-[#0A0A0A] border-white/10 text-white rounded-lg resize-none font-mono text-sm"
                    />
                    
                    <div className="flex gap-3">
                      {/* Photo */}
                      <div className="flex-1">
                        {editingItem.photo_url ? (
                          <div className="relative">
                            <img src={editingItem.photo_url} alt="" className="w-full h-24 object-cover rounded-lg" />
                            <button
                              type="button"
                              onClick={() => setEditingItem({ ...editingItem, photo_url: null })}
                              className="absolute top-1 right-1 bg-black/50 p-1 rounded"
                            >
                              <XCircle className="w-4 h-4 text-white" />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => photoInputRef.current?.click()}
                            disabled={uploadingPhoto}
                            className="w-full h-24 border border-dashed border-white/20 rounded-lg flex flex-col items-center justify-center gap-1 text-[#52525B] hover:border-[#10B981] hover:text-[#10B981]"
                          >
                            {uploadingPhoto ? (
                              <div className="w-5 h-5 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
                            ) : (
                              <>
                                <Camera className="w-5 h-5" />
                                <span className="text-xs">Фото</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                      
                      {/* File */}
                      <div className="flex-1">
                        {editingItem.file_url ? (
                          <div className="relative h-24 bg-[#0A0A0A] rounded-lg flex items-center justify-center">
                            <FileText className="w-6 h-6 text-[#7C3AED]" />
                            <button
                              type="button"
                              onClick={() => setEditingItem({ ...editingItem, file_url: null })}
                              className="absolute top-1 right-1 bg-black/50 p-1 rounded"
                            >
                              <XCircle className="w-4 h-4 text-white" />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={uploadingFile}
                            className="w-full h-24 border border-dashed border-white/20 rounded-lg flex flex-col items-center justify-center gap-1 text-[#52525B] hover:border-[#7C3AED] hover:text-[#7C3AED]"
                          >
                            {uploadingFile ? (
                              <div className="w-5 h-5 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
                            ) : (
                              <>
                                <FileText className="w-5 h-5" />
                                <span className="text-xs">Файл</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                    
                    <Button
                      onClick={handleSaveEdit}
                      disabled={saving}
                      className="w-full bg-[#10B981] hover:bg-[#059669] text-white rounded-lg"
                    >
                      {saving ? "Сохранение..." : "Сохранить"}
                    </Button>
                  </div>
                ) : (
                  // View mode
                  <div>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs text-[#52525B]">#{index + 1}</span>
                          {item.photo_url && (
                            <span className="text-xs text-[#10B981] flex items-center gap-1">
                              <Camera className="w-3 h-3" /> Фото
                            </span>
                          )}
                          {item.file_url && (
                            <span className="text-xs text-[#7C3AED] flex items-center gap-1">
                              <FileText className="w-3 h-3" /> Файл
                            </span>
                          )}
                        </div>
                        
                        {item.text && (
                          <p className="text-white text-sm font-mono bg-[#0A0A0A] rounded-lg p-2 break-all">
                            {item.text.length > 100 ? item.text.substring(0, 100) + "..." : item.text}
                          </p>
                        )}
                        
                        <div className="flex gap-2 mt-2">
                          {item.photo_url && (
                            <img src={item.photo_url} alt="" className="w-16 h-16 object-cover rounded-lg" />
                          )}
                          {item.file_url && (
                            <a 
                              href={item.file_url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-xs text-[#7C3AED] hover:text-[#A78BFA]"
                            >
                              <Download className="w-3 h-3" /> Скачать файл
                            </a>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setEditingItem(item)}
                          className="p-2 text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-lg"
                          title="Редактировать"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id)}
                          disabled={deleting === item.id}
                          className="p-2 text-[#EF4444] hover:text-[#F87171] hover:bg-[#EF4444]/10 rounded-lg"
                          title="Удалить"
                        >
                          {deleting === item.id ? (
                            <div className="w-4 h-4 border-2 border-[#EF4444] border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="flex justify-between items-center mt-4 pt-4 border-t border-white/5">
          <span className="text-[#71717A] text-sm">
            Всего: {stockItems.length} шт.
          </span>
          <Button
            onClick={onClose}
            variant="outline"
            className="bg-transparent border-white/10 text-white rounded-xl"
          >
            Закрыть
          </Button>
        </div>

        {/* Hidden inputs */}
        <input
          ref={photoInputRef}
          type="file"
          accept="image/*"
          onChange={handlePhotoUpload}
          className="hidden"
        />
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.pdf,.txt"
          onChange={handleFileUpload}
          className="hidden"
        />
      </div>
    </div>
  );
}

// Shop Orders Tab
function ShopOrdersTab({ token }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    try {
      const response = await axios.get(`${API}/shop/orders`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setOrders(response.data);
    } catch (error) {
      console.error("Failed to fetch orders:", error);
    } finally {
      setLoading(false);
    }
  };

  const filteredOrders = orders.filter(order => {
    if (filter === "instant") return order.purchase_type === "instant";
    if (filter === "guarantor") return order.purchase_type === "guarantor";
    if (filter === "pending") return order.status === "pending";
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      {/* Filters */}
      <div className="flex gap-2 mb-4">
        {[
          { key: "all", label: "Все" },
          { key: "instant", label: "Мгновенные" },
          { key: "guarantor", label: "Через Гаранта" },
          { key: "pending", label: "Ожидают выдачи" }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === f.key
                ? "bg-[#7C3AED]/15 text-[#A78BFA]"
                : "text-[#71717A] hover:text-white hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filteredOrders.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-xl p-12 text-center">
          <Package className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Нет заказов</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredOrders.map(order => (
            <div key={order.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="text-white font-medium">Заказ #{order.id.slice(0, 8)}</span>
                  <span className={`px-2 py-0.5 text-xs rounded-full ${
                    order.purchase_type === "instant" 
                      ? "bg-[#10B981]/10 text-[#10B981]" 
                      : "bg-[#7C3AED]/10 text-[#A78BFA]"
                  }`}>
                    {order.purchase_type === "instant" ? "Мгновенная" : "Гарант"}
                  </span>
                  <span className={`px-2 py-0.5 text-xs rounded-full ${
                    order.status === "completed" 
                      ? "bg-[#10B981]/10 text-[#10B981]" 
                      : order.status === "pending"
                      ? "bg-[#F59E0B]/10 text-[#F59E0B]"
                      : "bg-[#52525B]/10 text-[#71717A]"
                  }`}>
                    {order.status === "completed" ? "Выдан" : order.status === "pending" ? "Ожидает" : order.status}
                  </span>
                </div>
                <span className="text-[#52525B] text-xs">
                  {new Date(order.created_at).toLocaleString("ru-RU")}
                </span>
              </div>
              <div className="text-sm text-[#A1A1AA] mb-2">
                Покупатель: <span className="text-white">@{order.buyer_nickname}</span> | 
                {order.quantity > 1 ? ` ${order.quantity}x ` : " "}
                {order.product_name}
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#71717A]">
                  Сумма: <span className="text-white font-mono">{order.total_price} USDT</span>
                </span>
                <span className="text-[#71717A]">
                  К вам: <span className="text-[#10B981] font-mono">{order.seller_receives?.toFixed(2)} USDT</span>
                  <span className="text-[#52525B] text-xs ml-1">(комиссия: {order.commission?.toFixed(2)})</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Shop Finances Tab
function ShopFinancesTab({ token, shopBalance }) {
  const [finances, setFinances] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showWithdraw, setShowWithdraw] = useState(false);

  useEffect(() => {
    fetchFinances();
  }, []);

  const fetchFinances = async () => {
    try {
      const response = await axios.get(`${API}/shop/finances`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setFinances(response.data);
    } catch (error) {
      console.error("Failed to fetch finances:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      {/* Balance Card */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[#71717A] text-sm mb-1">Ваш торговый баланс</div>
            <div className="text-3xl font-bold text-[#10B981] font-mono">
              {finances?.balance?.toFixed(2) || shopBalance?.toFixed(2) || "0.00"} USDT
            </div>
            <div className="text-[#52525B] text-xs mt-1">
              Комиссия магазина: {finances?.commission_rate || 5}%
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => setShowWithdraw(true)}
              className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl"
            >
              Вывести средства
            </Button>
          </div>
        </div>
      </div>

      {/* Recent Sales */}
      <h3 className="text-white font-semibold mb-3">История операций</h3>
      {finances?.sales?.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-xl p-8 text-center">
          <p className="text-[#71717A]">Нет операций</p>
        </div>
      ) : (
        <div className="space-y-2">
          {finances?.sales?.slice(0, 20).map(sale => (
            <div key={sale.id} className="bg-[#121212] border border-white/5 rounded-lg p-3 flex items-center justify-between">
              <div>
                <div className="text-white text-sm">{sale.product_name}</div>
                <div className="text-[#52525B] text-xs">
                  {new Date(sale.created_at).toLocaleString("ru-RU")} | {sale.purchase_type === "instant" ? "Автовыдача" : "Гарант"}
                </div>
              </div>
              <div className="text-right">
                <div className="text-[#10B981] font-mono">+{sale.seller_receives?.toFixed(2)} USDT</div>
                <div className="text-[#52525B] text-xs">комиссия: {sale.commission?.toFixed(2)}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Withdraw Modal */}
      {showWithdraw && (
        <WithdrawModal
          token={token}
          balance={finances?.balance || shopBalance || 0}
          onClose={() => setShowWithdraw(false)}
          onSuccess={() => { setShowWithdraw(false); fetchFinances(); }}
        />
      )}
    </div>
  );
}

// Shop Settings Tab
function ShopSettingsTab({ token, shop, onUpdate }) {
  const [loading, setLoading] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingBanner, setUploadingBanner] = useState(false);
  const logoInputRef = useRef(null);
  const bannerInputRef = useRef(null);
  
  const [settings, setSettings] = useState({
    shop_logo: shop?.logo || "",
    shop_banner: shop?.banner || "",
    shop_description: shop?.description || "",
    allow_direct_purchase: shop?.allow_direct_purchase !== false
  });

  const handleUpload = async (file, type) => {
    const setUploading = type === "logo" ? setUploadingLogo : setUploadingBanner;
    setUploading(true);
    
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await axios.post(`${API}/shop/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      
      const field = type === "logo" ? "shop_logo" : "shop_banner";
      setSettings({ ...settings, [field]: response.data.url });
      
      // Save immediately
      await axios.put(`${API}/shop/settings?${field}=${encodeURIComponent(response.data.url)}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(type === "logo" ? "Логотип обновлён" : "Баннер обновлён");
      onUpdate();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка загрузки");
    } finally {
      setUploading(false);
    }
  };

  const saveSettings = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (settings.shop_description) params.append("shop_description", settings.shop_description);
      params.append("allow_direct_purchase", settings.allow_direct_purchase);
      
      await axios.put(`${API}/shop/settings?${params.toString()}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success("Настройки сохранены");
      onUpdate();
    } catch (error) {
      toast.error("Ошибка сохранения");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Shop Logo */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Логотип магазина</h3>
        <div className="flex items-center gap-6">
          <div 
            onClick={() => logoInputRef.current?.click()}
            className="w-24 h-24 bg-[#1A1A1A] border-2 border-dashed border-white/20 rounded-xl flex items-center justify-center cursor-pointer hover:border-[#10B981] transition-colors overflow-hidden"
          >
            {settings.shop_logo ? (
              <img src={settings.shop_logo} alt="Logo" className="w-full h-full object-cover" />
            ) : uploadingLogo ? (
              <div className="animate-spin w-6 h-6 border-2 border-[#10B981] border-t-transparent rounded-full" />
            ) : (
              <Camera className="w-8 h-8 text-[#52525B]" />
            )}
          </div>
          <input
            ref={logoInputRef}
            type="file"
            accept="image/*"
            onChange={(e) => e.target.files[0] && handleUpload(e.target.files[0], "logo")}
            className="hidden"
          />
          <div>
            <p className="text-sm text-white mb-1">Загрузите логотип вашего магазина</p>
            <p className="text-xs text-[#71717A]">JPG, PNG или WebP. Рекомендуемый размер: 200x200px</p>
            {settings.shop_logo && (
              <button
                onClick={() => setSettings({ ...settings, shop_logo: "" })}
                className="text-xs text-[#EF4444] hover:text-[#F87171] mt-2"
              >
                Удалить логотип
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Shop Banner */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Баннер магазина</h3>
        <div 
          onClick={() => bannerInputRef.current?.click()}
          className="w-full h-32 bg-[#1A1A1A] border-2 border-dashed border-white/20 rounded-xl flex items-center justify-center cursor-pointer hover:border-[#10B981] transition-colors overflow-hidden"
        >
          {settings.shop_banner ? (
            <img src={settings.shop_banner} alt="Banner" className="w-full h-full object-cover" />
          ) : uploadingBanner ? (
            <div className="animate-spin w-6 h-6 border-2 border-[#10B981] border-t-transparent rounded-full" />
          ) : (
            <div className="text-center">
              <Image className="w-8 h-8 text-[#52525B] mx-auto mb-2" />
              <p className="text-xs text-[#71717A]">Нажмите для загрузки баннера</p>
            </div>
          )}
        </div>
        <input
          ref={bannerInputRef}
          type="file"
          accept="image/*"
          onChange={(e) => e.target.files[0] && handleUpload(e.target.files[0], "banner")}
          className="hidden"
        />
        <p className="text-xs text-[#71717A] mt-2">Рекомендуемый размер: 1200x300px</p>
      </div>

      {/* Description */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Описание магазина</h3>
        <Textarea
          value={settings.shop_description}
          onChange={(e) => setSettings({ ...settings, shop_description: e.target.value })}
          placeholder="Расскажите о вашем магазине..."
          rows={4}
          className="bg-[#0A0A0A] border-white/10 text-white rounded-xl resize-none"
        />
      </div>

      {/* Purchase Settings */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Настройки покупок</h3>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-white">Разрешить прямые покупки</div>
            <div className="text-xs text-[#71717A]">Если выключено, покупки возможны только через гаранта</div>
          </div>
          <button
            type="button"
            onClick={() => setSettings({ ...settings, allow_direct_purchase: !settings.allow_direct_purchase })}
            className={`w-12 h-6 rounded-full transition-colors ${settings.allow_direct_purchase ? 'bg-[#10B981]' : 'bg-[#27272A]'}`}
          >
            <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.allow_direct_purchase ? 'translate-x-6' : 'translate-x-0.5'}`} />
          </button>
        </div>
      </div>

      {/* Save Button */}
      <Button
        onClick={saveSettings}
        disabled={loading}
        className="w-full bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-12"
      >
        {loading ? "Сохранение..." : "Сохранить настройки"}
      </Button>
    </div>
  );
}

// Shop Messages Tab
function ShopMessagesTab({ token, shopName }) {
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchConversations();
  }, []);

  const fetchConversations = async () => {
    try {
      const response = await axios.get(`${API}/shop/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversations(response.data);
    } catch (error) {
      console.error("Error fetching conversations:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchConversation = async (convId) => {
    try {
      const response = await axios.get(`${API}/shop/messages/${convId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSelectedConversation(response.data);
      setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (error) {
      toast.error("Ошибка загрузки переписки");
    }
  };

  const sendReply = async () => {
    if (!newMessage.trim() || !selectedConversation) return;
    
    setSending(true);
    try {
      await axios.post(
        `${API}/shop/messages/${selectedConversation.id}/reply`,
        { message: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage("");
      await fetchConversation(selectedConversation.id);
      fetchConversations();
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[600px]">
      {/* Conversations List */}
      <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-white/5">
          <h3 className="text-white font-semibold">Сообщения</h3>
          <p className="text-xs text-[#71717A]">От имени: {shopName}</p>
        </div>
        <div className="overflow-y-auto max-h-[520px]">
          {conversations.length === 0 ? (
            <div className="p-6 text-center">
              <MessageCircle className="w-8 h-8 text-[#52525B] mx-auto mb-2" />
              <p className="text-[#71717A] text-sm">Нет сообщений</p>
            </div>
          ) : conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => fetchConversation(conv.id)}
              className={`w-full p-4 text-left border-b border-white/5 hover:bg-white/5 transition-colors ${
                selectedConversation?.id === conv.id ? 'bg-[#10B981]/10' : ''
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-white font-medium text-sm">{conv.customer_nickname}</span>
                {conv.unread_shop > 0 && (
                  <span className="bg-[#10B981] text-white text-xs px-2 py-0.5 rounded-full">
                    {conv.unread_shop}
                  </span>
                )}
              </div>
              <p className="text-[#71717A] text-xs truncate">
                {conv.messages?.[conv.messages.length - 1]?.message || "Нет сообщений"}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="lg:col-span-2 bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
        {!selectedConversation ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <MessageCircle className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
              <p className="text-[#71717A]">Выберите переписку</p>
            </div>
          </div>
        ) : (
          <>
            {/* Chat Header */}
            <div className="p-4 border-b border-white/5">
              <h3 className="text-white font-semibold">{selectedConversation.customer_nickname}</h3>
              <p className="text-xs text-[#71717A]">Вы отвечаете от имени {shopName}</p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {selectedConversation.messages?.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.sender_type === 'shop' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[70%] rounded-xl px-4 py-2 ${
                    msg.sender_type === 'shop'
                      ? 'bg-[#10B981] text-white'
                      : 'bg-[#1A1A1A] text-white'
                  }`}>
                    <p className="text-xs opacity-70 mb-1">{msg.sender_name}</p>
                    <p className="text-sm">{msg.message}</p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Reply Input */}
            <div className="p-4 border-t border-white/5">
              <div className="flex gap-2">
                <Input
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Ответить от имени магазина..."
                  className="flex-1 bg-[#0A0A0A] border-white/10 text-white rounded-xl"
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendReply()}
                />
                <Button
                  onClick={sendReply}
                  disabled={sending || !newMessage.trim()}
                  className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl px-4"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Withdraw Modal
function WithdrawModal({ token, balance, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    amount: "",
    method: "card",
    details: ""
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await axios.post(
        `${API}/shop/withdraw?amount=${formData.amount}&method=${formData.method}&details=${encodeURIComponent(formData.details)}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Заявка на вывод отправлена");
      onSuccess();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания заявки");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold text-white mb-4">Вывод средств</h3>
        <p className="text-[#71717A] text-sm mb-4">
          Доступно: <span className="text-[#10B981] font-mono">{balance?.toFixed(2)} USDT</span>
        </p>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-[#A1A1AA] mb-1">Сумма (USDT)</label>
            <Input
              type="number"
              step="0.01"
              min="1"
              max={balance}
              value={formData.amount}
              onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
              className="bg-[#0A0A0A] border-white/10 text-white rounded-xl"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm text-[#A1A1AA] mb-1">Способ вывода</label>
            <select
              value={formData.method}
              onChange={(e) => setFormData({ ...formData, method: e.target.value })}
              className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl"
            >
              <option value="card">Банковская карта</option>
              <option value="crypto">Криптовалюта</option>
              <option value="other">Другое</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm text-[#A1A1AA] mb-1">Реквизиты</label>
            <Textarea
              value={formData.details}
              onChange={(e) => setFormData({ ...formData, details: e.target.value })}
              placeholder="Номер карты, адрес кошелька и т.д."
              rows={3}
              className="bg-[#0A0A0A] border-white/10 text-white rounded-xl resize-none"
              required
            />
          </div>
          
          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="flex-1 bg-transparent border-white/10 text-white rounded-xl"
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className="flex-1 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl"
            >
              {loading ? "Отправка..." : "Отправить заявку"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Main Component
export default function TraderShop() {
  const { token } = useAuth();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStatus(response.data);
    } catch (error) {
      console.error("Failed to fetch shop status:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Has approved shop
  if (status?.has_shop) {
    return <ShopManagement />;
  }

  // No shop yet - show application chat
  return <ShopApplicationChat onSuccess={fetchStatus} />;
}
