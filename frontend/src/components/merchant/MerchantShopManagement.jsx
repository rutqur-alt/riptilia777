import { useState, useEffect } from "react";
import axios from "axios";
import { Download, Edit, Loader, Package, Plus, Store, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth, API } from "@/App";

const SHOP_CATEGORIES = {
  accounts: "Аккаунты",
  software: "Софт",
  databases: "Базы данных",
  tools: "Инструменты",
  guides: "Гайды и схемы",
  keys: "Ключи",
  financial: "Финансовое",
  templates: "Шаблоны",
  games: "Игры",
  subscriptions: "Подписки",
  services: "Услуги",
  other: "Другое"
};

export default function MerchantShopManagement() {
  const { token, user } = useAuth();
  const [products, setProducts] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [addingStock, setAddingStock] = useState(null);
  const [showWithdraw, setShowWithdraw] = useState(false);
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [withdrawing, setWithdrawing] = useState(false);
  const [productForm, setProductForm] = useState({ name: "", description: "", price: "", currency: "USDT", category: "accounts", type: "digital", delivery_text: "" });
  const [stockText, setStockText] = useState("");

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [dashboardRes, productsRes] = await Promise.all([
        axios.get(`${API}/shop/dashboard`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/shop/products`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setDashboard(dashboardRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddProduct = async () => {
    if (!productForm.name || !productForm.price) { toast.error("Заполните название и цену"); return; }
    try {
      if (editingProduct) {
        await axios.put(`${API}/shop/products/${editingProduct.id}`, productForm, { headers: { Authorization: `Bearer ${token}` } });
        toast.success("Товар обновлён");
      } else {
        await axios.post(`${API}/shop/products`, productForm, { headers: { Authorization: `Bearer ${token}` } });
        toast.success("Товар добавлен");
      }
      setShowAddProduct(false); setEditingProduct(null);
      setProductForm({ name: "", description: "", price: "", currency: "USDT", category: "accounts", type: "digital", delivery_text: "" });
      fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || "Ошибка"); }
  };

  const handleDeleteProduct = async (productId) => {
    if (!confirm("Удалить товар?")) return;
    try {
      await axios.delete(`${API}/shop/products/${productId}`, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Товар удалён"); fetchData();
    } catch (error) { toast.error("Ошибка удаления"); }
  };

  const handleAddStock = async (productId) => {
    if (!stockText.trim()) return;
    const items = stockText.split("\n").filter(s => s.trim());
    try {
      await axios.post(`${API}/shop/products/${productId}/stock`, { items }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Добавлено ${items.length} единиц`);
      setAddingStock(null); setStockText(""); fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || "Ошибка"); }
  };

  const handleWithdraw = async () => {
    const amount = parseFloat(withdrawAmount);
    if (!amount || amount <= 0) { toast.error("Введите корректную сумму"); return; }
    setWithdrawing(true);
    try {
      await axios.post(`${API}/shop/withdraw?amount=${amount}&method=to_balance&details=${encodeURIComponent("На баланс аккаунта")}`, {}, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`${amount} USDT переведено на баланс аккаунта`);
      setShowWithdraw(false); setWithdrawAmount(""); fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || "Ошибка вывода"); }
    finally { setWithdrawing(false); }
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>;
  }

  const shopBalance = dashboard?.shop?.shop_balance || 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Мой магазин</h1>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-[#10B981]/10 rounded-2xl flex items-center justify-center"><Store className="w-7 h-7 text-[#10B981]" /></div>
            <div>
              <div className="text-lg font-bold text-white">{dashboard?.shop?.shop_name || "Магазин"}</div>
              <div className="text-sm text-[#71717A]">{dashboard?.shop?.shop_description || ""}</div>
            </div>
          </div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <div className="text-sm text-[#71717A] mb-1">Баланс магазина</div>
          <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">{shopBalance.toFixed(2)} USDT</div>
          {shopBalance > 0 && (
            <button onClick={() => setShowWithdraw(true)} className="mt-3 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl h-9 px-4 text-sm inline-flex items-center gap-2">
              <Download className="w-4 h-4" />Вывести на баланс
            </button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-white">{dashboard?.total_products || 0}</div>
          <div className="text-xs text-[#71717A]">Товаров</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-white">{dashboard?.total_sales || 0}</div>
          <div className="text-xs text-[#71717A]">Продаж</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">{(dashboard?.total_revenue || 0).toFixed(2)}</div>
          <div className="text-xs text-[#71717A]">Выручка USDT</div>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-white">Товары ({products.length})</h3>
        <button onClick={() => { setEditingProduct(null); setProductForm({ name: "", description: "", price: "", currency: "USDT", category: "accounts", type: "digital", delivery_text: "" }); setShowAddProduct(true); }} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-9 px-4 text-sm inline-flex items-center gap-2">
          <Plus className="w-4 h-4" />Добавить товар
        </button>
      </div>
      {products.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 text-center py-10">
          <Package className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
          <p className="text-[#71717A]">Нет товаров. Добавьте первый товар!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {products.map(p => (
            <div key={p.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">{p.name}</div>
                  <div className="text-sm text-[#71717A] mt-1">{p.description?.slice(0, 80)}</div>
                  <div className="flex items-center gap-4 mt-2">
                    <span className="text-[#10B981] font-medium font-['JetBrains_Mono']">{p.price} {p.currency || "USDT"}</span>
                    <span className="text-xs text-[#71717A]">В наличии: {p.stock_count ?? p.quantity ?? 0}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-white/5 text-[#71717A]">{SHOP_CATEGORIES[p.category] || p.category}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => setAddingStock(p)} className="text-[#10B981] hover:bg-[#10B981]/10 rounded-lg p-2" title="Добавить товар"><Plus className="w-4 h-4" /></button>
                  <button onClick={() => { setEditingProduct(p); setProductForm({ name: p.name, description: p.description || "", price: p.price, currency: p.currency || "USDT", category: p.category || "accounts", type: p.type || "digital", delivery_text: p.delivery_text || "" }); setShowAddProduct(true); }} className="text-[#3B82F6] hover:bg-[#3B82F6]/10 rounded-lg p-2" title="Редактировать"><Edit className="w-4 h-4" /></button>
                  <button onClick={() => handleDeleteProduct(p.id)} className="text-[#EF4444] hover:bg-[#EF4444]/10 rounded-lg p-2" title="Удалить"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {showAddProduct && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-white mb-4">{editingProduct ? "Редактировать товар" : "Добавить товар"}</h3>
            <div className="space-y-3">
              <div><label className="text-sm text-[#A1A1AA] mb-1 block">Название *</label><input value={productForm.name} onChange={(e) => setProductForm({...productForm, name: e.target.value})} className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" placeholder="Название товара" /></div>
              <div><label className="text-sm text-[#A1A1AA] mb-1 block">Описание</label><textarea value={productForm.description} onChange={(e) => setProductForm({...productForm, description: e.target.value})} className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl resize-none min-h-[80px]" placeholder="Описание товара" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-sm text-[#A1A1AA] mb-1 block">Цена *</label><input type="number" step="0.01" value={productForm.price} onChange={(e) => setProductForm({...productForm, price: e.target.value})} className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" placeholder="0.00" /></div>
                <div><label className="text-sm text-[#A1A1AA] mb-1 block">Категория</label><select value={productForm.category} onChange={(e) => setProductForm({...productForm, category: e.target.value})} className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl">{Object.entries(SHOP_CATEGORIES).map(([k, v]) => (<option key={k} value={k}>{v}</option>))}</select></div>
              </div>
              <div><label className="text-sm text-[#A1A1AA] mb-1 block">Текст после покупки</label><textarea value={productForm.delivery_text} onChange={(e) => setProductForm({...productForm, delivery_text: e.target.value})} className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl resize-none" placeholder="Что получит покупатель" /></div>
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => { setShowAddProduct(false); setEditingProduct(null); }} className="flex-1 bg-transparent border border-white/10 text-white rounded-xl h-10">Отмена</button>
              <button onClick={handleAddProduct} className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10">{editingProduct ? "Сохранить" : "Добавить"}</button>
            </div>
          </div>
        </div>
      )}
      {addingStock && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-2">Добавить товар: {addingStock.name}</h3>
            <p className="text-sm text-[#71717A] mb-4">Каждая строка = 1 единица товара</p>
            <textarea value={stockText} onChange={(e) => setStockText(e.target.value)} className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl resize-none min-h-[150px] font-mono text-sm" placeholder={"login:password\nlogin2:password2\n..."} />
            <div className="flex gap-3 mt-4">
              <button onClick={() => { setAddingStock(null); setStockText(""); }} className="flex-1 bg-transparent border border-white/10 text-white rounded-xl h-10">Отмена</button>
              <button onClick={() => handleAddStock(addingStock.id)} className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10">Добавить ({stockText.split("\n").filter(s => s.trim()).length} шт)</button>
            </div>
          </div>
        </div>
      )}
      {showWithdraw && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-2">Вывод на баланс аккаунта</h3>
            <p className="text-sm text-[#71717A] mb-4">Доступно: <span className="text-[#10B981] font-mono">{shopBalance.toFixed(2)} USDT</span></p>
            <p className="text-xs text-[#A1A1AA] mb-4">Средства будут переведены на ваш основной баланс аккаунта</p>
            <div><label className="text-sm text-[#A1A1AA] mb-1 block">Сумма (USDT)</label><input type="number" step="0.01" min="0.01" max={shopBalance} value={withdrawAmount} onChange={(e) => setWithdrawAmount(e.target.value)} className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" placeholder="0.00" /></div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => { setShowWithdraw(false); setWithdrawAmount(""); }} className="flex-1 bg-transparent border border-white/10 text-white rounded-xl h-10">Отмена</button>
              <button onClick={handleWithdraw} disabled={withdrawing} className="flex-1 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl h-10">{withdrawing ? "Вывод..." : "Вывести на баланс"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

