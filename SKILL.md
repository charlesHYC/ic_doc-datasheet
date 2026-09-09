---
name: ic-datasheet
description: Use when the user asks for a datasheet, spec sheet, or design manual for a Verilog/SystemVerilog project - a printable A4 document with module symbols, pin tables, a connectivity block diagram, timing waveforms and a register map, in the style of a foundry IP datasheet (ARM Artisan memory compiler). Distinct from a screen-oriented HTML design document; this one produces a print-oriented datasheet.
metadata:
  short-description: Generate an A4 datasheet for a Verilog project
---

# ic-datasheet — Verilog 專案 datasheet 產生器

產生一份可列印成 A4 PDF 的 datasheet，風格對標 foundry IP datasheet（ARM Artisan memory
compiler 那種），但**不做 process corner 的細部參數表**。

產出是**兩個檔**：HTML（可改、可重跑）與 A4 PDF（可寄、可印）。

## 呼叫方式

```
/ic-datasheet <專案名稱或 RTL 目錄>
```

這個 skill 產的是**印出來的 datasheet**（A4 分頁、頁碼、黑白、Times）。如果要的是螢幕上
讀的設計文件（sticky sidebar、彩色架構圖、可捲動），那是另一種東西，不要混用樣式。

---

## 分工原則（最重要的一條）

| 類型 | 來源 | 重跑時 |
|---|---|---|
| 事實：parameter、port、位寬、實體化關係 | 從 RTL 抽 | **會更新** |
| 文字：Overview、Description、每個訊號的用途 | 人寫，放在 `build.py` 的 `PROSE` dict | **不會被蓋掉** |

不要試圖從 RTL 自動生成描述文字，那只會產出「`wr_go` is the wr_go signal」這種廢話。
**文字一律自己寫，而且要寫出「為什麼」**，例如「這些 register slice 不是裝飾品：少了它，
從記憶體控制器到 write engine 的路徑會 miss timing 半個 ns」。

## 事實一定要去核對，不要憑記憶

暫存器表、位元欄位、位寬這類東西，**一律回去讀 RTL 再寫**。

- 暫存器位址：讀 AXI-Lite 的位址解碼（`case (axil_addr[N:2])` 這類），位址 = 選擇碼 × 4
- 位元欄位：寫入分支看 `csr_* <= wdata[n]`，讀取分支看回傳的串接式
- 自清 / 保持 / 讀清 這三種語意要分清楚並寫進表格

---

## 工作流程

1. **抽 header**
   ```sh
   python3 scripts/extract.py <file1>.v <file2>.v ... > modules.json
   ```
   輸出每個 module 的 name / params / ports / localparams / instantiates。
   banner 註解（`// ---- AXI write ----`）會被當成 port 分組標題。

   ANSI-2001（方向寫在 port list 裡）與 **Verilog-95**（header 只有名字、方向與
   位寬宣告在 module 內）兩種 header 都吃得下。memory compiler 與 vendor macro
   幾乎都是後者。只讀檔案裡的**第一個** module，讀到它的 `endmodule` 為止。

   ⚠️ **不要 glob `<rtl>/*.v`。** RTL 目錄常留著 `_v1` / `_v2` 之類的舊檔，而且
   **檔名跟 module 名不一定一致**。真實案例：某專案裡 `write_path.v` 宣告的
   module 叫 `write_path_v2`，而 `top.v` / `top_v1.v` / `top_v2.v` 三個檔都宣告
   同一個 module 名。glob 會抽到已作廢的版本，而且產出看起來完全正常。

   **權威檔案清單去合成腳本拿**，例如 Vivado：
   ```sh
   grep -oP '<rtl 目錄>/\K[\w.]+\.v' <proj>.runs/synth_1/<proj>.tcl | sort -u
   ```
   其他流程就去讀對應的 filelist / Makefile。再用
   `grep -m1 -oP '^\s*module\s+\K\w+' <file>` 確認每個檔真正宣告的 module 名。

2. **決定收錄哪些 module。** 要求「所有 module」時就是**全部**，包含 library 模組。
   自己寫的模組給完整章節（symbol + pin table + 波形 + 描述）；framework 或 library 模組
   （第三方 IP、`axis_fifo` 這類）放一張「Library modules」表帶過，註明來源與在本設計中
   的角色即可。port 數超過 100 的外殼模組不要畫 pin table，直接說明「port list 由
   framework 定義，故省略」。

3. **寫 PROSE。** 每個模組 2–3 段。

4. **畫圖**（見下面「圖的規範」）。

5. **組檔 + 驗證**
   ```sh
   python3 build.py
   ```
   然後**一定要跑驗證迴圈**（見下面）。

6. **轉 PDF**
   ```sh
   python3 scripts/topdf.py <design>_datasheet_manual.html --check     # 先驗每頁放得下
   python3 scripts/topdf.py <design>_datasheet_manual.html             # 288 dpi
   python3 scripts/topdf.py <design>_datasheet_manual.html --scale 2   # 192 dpi，檔案較小
   ```
   30 頁約需十來分鐘（每頁跑一次 headless 瀏覽器）。

---

## 文件結構（頁序）

1. 封面頁：專案標題、副標、修訂版、一段 Overview、關鍵數據表
2. Block diagram（整個系統怎麼接）
3. Hierarchy（誰包含誰）
4. 每個主要模組一章：Description → Parameters → Symbol → Pins
5. 外殼模組 + 暫存器表
6. Library modules 表
7. Timing（波形）

---

## 排版規範

字級階層：**標題大、內文小，而內文裡的小標題要大於內文**。

| 元素 | 字級 |
|---|---|
| 封面主標 | 19pt bold |
| 封面副標 | 12pt |
| 章節標題 h2 | 13pt bold |
| h2 後面的檔名註記 | 9.2pt，同一行，`margin-left:3mm` |
| 內文 | 11pt |
| 表格 | 9.6pt（表頭 9.8pt） |
| **表格內的分組小標** | **10.6pt bold**（要大於表格內文） |
| 圖說 figcaption | 9.4pt |
| 註記 .note | 9.6pt 灰 |
| 頁尾 | 8.6pt |

其他：

- **字體一律 `"Times New Roman", Times, serif`**，包含表格裡的訊號名（`.mono` 也是
  Times，不用等寬字）。**唯一例外是 module symbol 圖**，那張保留自己的字體。
- **標題自成一行，內文從左邊界齊頭開始。** 不要做「標題在左、內文縮排在右」的兩欄式
  ——那會在標題底下留一大塊空白，看起來像排版壞掉。
  `.band > h2 { margin-bottom:3mm }`，內文不要有 `margin-left`。
- 頁面 `@page { size:A4; margin:15mm 14mm 12mm }`，每頁 `display:flex; flex-direction:column`
  搭配 `footer { margin-top:auto }`，頁尾才會壓在底部。
- 表頭 `background:#6f6f6f; color:#fff`；分組列 `background:#e2e0dc`。
- 黑白，禁 emoji。

檔名：**`<design>_datasheet_manual.html`**。放一個 `README.md` 明講「要開哪一個檔」，
其餘都是產生器——不要讓人在一堆檔案裡猜。

---

## 圖的規範

三種圖，各有各的坑。共通原則：

> **SVG 的字看起來多大，取決於 viewBox 單位數與 `width="Nmm"` 的比值，不是 font-size。**
> 字太小的解法是**減少 viewBox 單位數**（少畫幾個 cycle、縮短座標），不是放大 font-size。
> 每張圖都要自己帶 `width="Nmm"`，不要靠 CSS 拉伸。

### Symbol（`build.py` 的 `symbol()`）

- 方塊置中，輸入在左、輸出在右
- AXI 訊號要**按 channel 併成一行**（`*_aw*` 一行、`*_w*` 一行…），不要一根 pin 一行，
  也不要把 AW/W/B 併成一條 `s_axi_*`
- 併完仍超過 13 行時，降一級改用 **interface 分組**顆粒度
- 標籤放不下寬度就**只留名字**，絕對不要從中間截斷成 `s_axis_dma_rd_status_tag [15:0`
- 訊號名左邊的溝槽要留夠（實測 94 單位才不會把第一個字母切掉）

### 波形（`scripts/wave.py`）

- **資料要真的來自模擬**：VCD，或 testbench 匯出的 handshake 表格。沒有資料就去找，
  不要說「這個模組沒有波形資料」——先確認過再說。
- 只畫**看得出行為的那幾個 cycle**，中間省略的用 datasheet 的斷開記號 `//` 表示。
  典型是「前 5 個 cycle + 延遲後的 6 個 cycle」兩段。
- **說明文字寫在 HTML 的 `<figcaption>`，不要寫進 SVG**——SVG 的 text 不會自動換行，
  一定會衝出右邊界。
- 每張圖用同一組單位尺寸（`CW/ROW` 常數），這樣不同圖的波形看起來一樣大。
  ⚠️ 注意 `render()` 內的 `mm = min(178, round(W * 0.252))`：**寬度超過約 706 單位就會被
  clamp**，那張圖的單位尺寸會比別張小。要一致就讓每張都待在 706 以內（減少 cycle 數，
  或縮小 `CW`）。

**匯流排一律照 datasheet 慣例畫，不可以畫成方框**（對標 ARM Artisan memory compiler
的 timing 圖）：

- 資料值之間用 **X 交叉**（兩條軌互換）表示切換，有效資料段是「`<` 值 `>`」的六角形，
  **不是**兩端各一條垂直線的長方形。
- 值不被在意的區間畫成**連續的 X 鏈**（don't care），不是留白也不是斜線底紋。
- **圖的左右邊界不封口**：軌線直接跑到邊界為止。匯流排不會在那裡開始或結束，
  是「圖」在那裡結束。同理，資料窗剛好切齊邊界時不畫交叉。
- 這些都在 `_bus()` / `_cross()` / `_dontcare()` 裡，spec 只要給 `windows`
  （`(起始 cycle, 結束 cycle, 標籤)`），沒被 window 蓋到的區間自動變成 don't care。
- 時脈的斜率刻意做得很小（`SLEW`）。在這個 cell 寬度下真的照 AC timing 圖那樣斜，
  會變成三角波。

### Block diagram（`scripts/blocks.py`）

- 畫**資料怎麼流**，跟 hierarchy 圖（誰包含誰）是兩張不同的圖，都要有
- **兩趟排版**：先放方塊、記下實際占用範圍，再回頭畫外框。外框高度寫死一定會漏掉東西
- 箭頭上的標籤要確認**真的有空間**。方塊之間的縫小於文字寬度時，
  是去把縫加寬，不是硬塞

---

## 驗證迴圈（不可跳過）

改完圖一定要看過再回報。

```sh
WD=$PWD    # --screenshot 一定要絕對路徑
MOZ_HEADLESS=1 timeout 300 firefox --headless \
  --screenshot "$WD/out.png" --window-size=1000,3000 \
  "file://$WD/<design>_datasheet_manual.html"
python3 -c "from PIL import Image; Image.open('$WD/out.png').crop((x0,y0,x1,y1)).save('$WD/c.png')"
```

⚠️ **`--screenshot` 給相對路徑時 firefox 不會報錯，也不會產生檔案。** 一律用絕對路徑。

然後把 PNG 看過。要檢查：文字有沒有被切掉、標籤有沒有壓到線、外框有沒有包住內容、
分頁有沒有把表格切斷。

Firefox 截圖在文件很長時會截斷（約 32767 px 上限），這時把單張圖獨立渲染成一個
小 HTML 再截。

---

## 分頁：`.page` 放不下不會有任何提示

**這是最容易漏掉、而且後果最嚴重的一個坑。**

`.page` 的 `min-height:297mm` 是**最小值**。內容太多時 div 就往下長，在螢幕上疊起來看
**完全正常**——頁尾照樣在該頁底部，看不出任何異狀。但那一頁已經不是 A4 了：Ctrl+P 會
重新分頁、頁尾跑到紙張中間，轉 PDF 則會被裁掉。

實例：`example/` 那份 datasheet 的第一版，16 頁裡有 **11 頁超出**，最嚴重一頁超出
310 mm（等於整整多一張紙），而螢幕上看起來毫無問題，完全沒被發現。

**做法**：

1. `build.py` 用 `scripts/paginate.py` 估高度，長表格自動拆頁：
   ```python
   thead, rows = pins_rows(m)                      # rows 是 (html, 估計高度)
   for part in pg.chunk(rows, pg.body_px(pg.BAND_PX + pg.THEAD_PX)):
       page('<div class="band wide"><h2>%s — pins</h2>%s</div>'
            % (name, wrap_rows(thead, part)), n)
   ```
   同一模組拆出多頁時，標題加 `(1 of 3)`。
2. Symbol、波形這類**不能被切開**的圖，用 `pg.svg_px()` 算出真實高度後，讓後面的表格
   接在同一頁（`pg.chunk(..., first=...)`），不要讓一張圖獨佔整頁留下大片空白。
   ⚠️ `pg.svg_px()` 預設讀 SVG 自己的 `width="Nmm"`；**symbol 圖是 `width="100%"`，
   寬度由 CSS 的 `.fig-sym svg{max-width:158mm}` 決定**，要傳 `width_mm=158`，
   否則估出來是 0，那一頁就會爆掉。
3. 估算一律**取悲觀值**（`paginate.py` 內建 `SAFETY_PX`）。估太鬆會掉內容，估太緊只是
   多一次分頁，代價不對等。
4. **最後一定要 `topdf.py --check` 實測**。估算只是讓你接近，實測才算數。
   有任何一頁超出時 `topdf.py` 會**拒絕轉檔**（要硬轉得加 `--force`，內容會被裁掉）。

## 轉 PDF 的做法與限制

**Firefox 沒有 `--print-to-pdf`**（`--help` 只列 `--screenshot`）。若系統上也沒有
chromium / wkhtmltopdf / weasyprint，就只能自己來：`scripts/topdf.py` 把每一頁單獨
渲染成高解析度 PNG，再拼成 A4 PDF。

- 放大用 **`transform: scale(N)`**，不是 `zoom`，也不是把 PNG 事後放大。transform 不會
  重排版面，所以 PDF 的排版跟你在螢幕上驗證過的**完全一致**，只是光柵化在更高解析度跑。
- `layout.css.devPixelsPerPx` 這個 pref 在 headless 截圖模式**無效**（prefs.js 和 user.js
  都試過），不要浪費時間。
- 產出是**點陣 PDF，文字不可選取**。要向量 PDF 只能換引擎（weasyprint 之類），但那會用
  另一套排版引擎重排，`display:flex` + `margin-top:auto` 的頁尾定位很可能跑掉——
  這裡的取捨是「排版保真」優先於「文字可選」。
- 檔案大小：實測 29 頁 288 dpi 為 11.8 MB；`--scale 2` 約四成。要寄信用 `--scale 2`。
- 若機器上有 Chromium 或 weasyprint，可以改用它們產向量 PDF，但務必重新跑一次
  `--check` 等級的檢查：換引擎等於換排版。

---

## 環境

- `extract.py` / `build.py` / `paginate.py` 需要 **Python 3.8+**
- `topdf.py` 需要 **Pillow** 與 **Firefox**
- ⚠️ 若機器上有多個 Python，Pillow 不一定裝在你跑 `build.py` 的那一個。
  兩支腳本用不同直譯器是常見情況，明確寫出路徑，不要假設 `python3` 到處都一樣。

## 附帶的腳本

| 檔案 | 通用程度 |
|---|---|
| `scripts/extract.py` | ✅ 完全通用，Verilog-95 與 Verilog-2001 header 都支援 |
| `scripts/paginate.py` | ✅ 完全通用。高度估算，讓 `build.py` 在超出前就把表格拆頁 |
| `scripts/topdf.py` | ✅ 完全通用。轉 PDF，並在轉檔前檢查每頁是否真的放得進 A4 |
| `scripts/wave.py` | renderer 通用；每張波形的 spec（哪些 cycle、哪些訊號）要照專案手寫 |
| `scripts/blocks.py` | 版面邏輯通用；資料流順序要照專案改 |

`example/build.py` 是一份實際專案的組檔程式，**複製後改**是最快的起手式。它有一半是
專案專屬的常數（`PROSE`、`CSR`、`LIB`、`FULL`），另一半是可直接沿用的：CSS（權威的
字級與版面）、`symbol()`、`params_rows()` / `pins_rows()` / `wrap_rows()`、
`resolve_params()`（把 `[NUM_CH*ID_WIDTH-1:0]` 這種算成 `[95:0]`，含 `$clog2`）、
以及整套分頁邏輯。

⚠️ `example/build.py` 與 `scripts/blocks.py`、`scripts/wave.py` 裡的**模組名稱與資料流
是匿名化過的範例**，不對應任何真實 `modules.json`，所以不能直接跑起來。它們是**範本**：
把名字、`PROSE`、`CSR` 換成你自己專案的，版面與邏輯照抄。
