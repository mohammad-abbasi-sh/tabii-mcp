# tabii-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/tabii-mcp

TRT'nin dijital yayın platformu tabii.com için resmi olmayan, **salt okunur** MCP sunucusu (2023'te yayına girdi, 11 milyondan fazla abone) — Türkçe diziler, filmler, belgeseller, çocuk içerikleri ve 15 canlı TRT kanalı. Orijinal Türkçe başlığa göre katalog araması, dizi/film detayları (sezonlar, bölümler, oyuncular, diller), canlı kanal HLS yayın adresleri ve oyuncu/ekip filmografileri.

> Mohammad Abbasi tarafından "Turkey MCP factory" (Sepehr tarzı hat) kapsamında geliştirildi. tabii.com veya TRT ile bağlantısı yoktur.

## Yapay zekâ ajanları için

MCP istemci yapılandırmanıza ekleyin (stdio):

```json
{
  "mcpServers": {
    "tabii": {
      "command": "uvx",
      "args": ["tabii-mcp==0.1.0"]
    }
  }
}
```

Veya yerelde çalıştırın: `python -m tabii_mcp.server` (`mcp<2`, `curl-cffi` gerekir).

## Araçlar

| Araç | Açıklama |
|------|----------|
| `tabii_search_content` | Katalogda orijinal Türkçe başlığa göre arama (örn. "gassal", "mevlana") — `language` ("tr" varsayılan, "en", "es", "ar", "ur"), `limit` 1..10; her sonuçta id, slug, yerelleştirilmiş başlık, orijinal başlık, tür, yıl ve URL |
| `tabii_get_show` | Bir içeriğin tüm detayı — `show_id` veya `slug` (örn. "gassal"); yerelleştirilmiş başlık, orijinal başlık, tür, yıl, türler (genre), yaş sınırı, bölüm başlıkları + süreleriyle sezonlar (en fazla 60 bölüm), oyuncular, yönetmenler, senaristler, açıklama, ses/altyazı dilleri, rozetler, fragman sayısı, URL |
| `tabii_homepage` | Ana sayfadaki güncel bölümler (tabii'ye Özel İçerikler, Dizi, Film, Belgesel, Çocuk) ve içerikleri — `language` |
| `tabii_live_channels` | 15 canlı TRT kanalı (TRT 1, TRT 2, TRT Belgesel, TRT Haber, TRT Spor, TRT Çocuk, TRT World, ...) — izleme URL'si ve herkese açık HLS yayın adresi |
| `tabii_get_person` | Bir oyuncu/ekip üyesi, sayısal kişi id'siyle (örn. Ahmet Kural 6774) — ad, görev ve tabii'deki filmografisi |
| `tabii_health` | Erişilebilirlik kontrolü (ana sayfa + bir herkese açık içerik) — ok / blocked / error |

Örnek çıktı (`tabii_search_content` / "gassal", dil "en"):

```json
{"id": 438813, "slug": "gassal", "title": "The Late Offices",
 "original_title": "Gassal", "content_type": "series", "made_year": 2024,
 "url": "https://www.tabii.com/en/detail/438813/gassal"}
```

## Nasıl çalışır?

tabii.com, giriş, API anahtarı ve oturum jetonu gerektirmeyen herkese açık bir katalog API'si sunar: `eu1.tabii.com/apigateway/catalog/v1/public/shows/{id}` ve `.../public/persons/{id}` (kimlik doğrulamalı sürümler — `search/v1`, `catalog/v1/show/{id}` — Bearer oturum jetonu olmadan HTTP 401 döner ve kullanılmaz). Ana sayfa sunucu taraflı Next.js ile oluşturulur; `__NEXT_DATA__` JSON'i öne çıkan bölümleri ve 15 canlı kanalı herkese açık HLS adresleriyle birlikte taşır. Arama, sitenin site haritalarını tarar (EN + TR birleştirilmiş: 1.306 içerik, 1.180 kişi — 6 saat önbellekli) ve en iyi eşleşmelerin yerelleştirilmiş başlıklarını herkese açık içerik API'siyle çözer. İki konu aşılmaya çalışılmaz, belgelenir: site haritaları kataloğun tamamını kapsamaz (bazı lisanslı içerikler, örn. Hobbit, ve bazı orijinaller eksik — id ile yine de erişilebilir, örn. ana sayfa bölümlerinden) ve tür/kategori sayfaları giriş gerektiren bir uç noktadan beslenen istemci taraflı kabuklardır, bu yüzden tür tarama aracı sunulmaz. Oynatma, giriş yapmış bir Tabii Premium oturumu gerektirir ve kapsam dışıdır — bu sunucu yalnızca katalog verisi sunar. Aktarım, Chrome TLS taklidi kullanır (`curl-cffi`, dönüşümlü); istekler ~0,8 sn aralıklarla yapılır; her şey salt okunurdur.

## Kurulum

```bash
uvx tabii-mcp==0.1.0        # doğrudan çalıştır (uv gerekir)
# veya
pip install tabii-mcp==0.1.0
tabii-mcp    # MCP sunucusunu stdio üzerinde başlatır
```

## Testler

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

Çevrimdışı testler kayıtlı örneklerle çalışır (11.11.2026'da çekilmiş gerçek sayfalar/API yanıtları); canlı testler tabii.com ve herkese açık API'ye bağlanır. Derleme anında testler geçti (sayılar için depoya bakın); ayrıca bir MCP stdio duman testi vardır.

## Yol haritası

- tabii oturumsuz bir uç nokta yayınlarsa tür tarama
- Ana sayfa bölümlerinden "bu hafta yeni" / yeni eklenenler akışı
- Bölüm düzeyinde detay (bölüm açıklaması, ses/altyazı parçaları)

## Lisans

MIT — bkz. [LICENSE](LICENSE).

---

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
