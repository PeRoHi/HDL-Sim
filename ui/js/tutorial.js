/**
 * HDL-Sim Tutorial Modal
 * - 初回起動時に自動表示
 * - Help > チュートリアルを表示 から再表示可能
 */
(function (global) {
  const TUTORIAL_SEEN_KEY = "hdl-sim-tutorial-seen";

  const STEPS = [
    {
      title: "HDL-Sim へようこそ！",
      icon: "🎉",
      body: `
        <p><strong>HDL-Sim</strong> は、ブラウザ上で動作する <strong>Verilog HDL シミュレータ</strong>です。</p>
        <ul>
          <li>Verilog ファイル (.v / .sv) を読み込み、シミュレーションを実行できます</li>
          <li>モジュール階層の確認や信号値の表示が可能です</li>
          <li>波形ビューアでシミュレーション結果を視覚的に確認できます</li>
          <li>プロジェクト (.spj) として保存・管理できます</li>
        </ul>
        <p class="tutorial-note">インストール不要。ブラウザだけで HDL の学習・実験ができます。</p>
      `,
    },
    {
      title: "プロジェクトの作り方",
      icon: "📁",
      body: `
        <p>HDL-Sim では <strong>プロジェクト (.spj)</strong> 単位でファイルを管理します。</p>
        <div class="tutorial-steps-list">
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">1</span>
            <div>
              <strong>新規プロジェクト作成</strong><br>
              左パネルの <code>New</code> ボタン、またはメニュー <code>Project → New...</code> で新しいプロジェクトを作成します。
            </div>
          </div>
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">2</span>
            <div>
              <strong>ファイルの追加</strong><br>
              <code>Open</code> ボタンでローカルの .v / .sv ファイルを読み込むか、<code>+ New</code> で空のファイルを新規作成します。
            </div>
          </div>
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">3</span>
            <div>
              <strong>プロジェクトとファイルの保存</strong><br>
              <code>Save</code> ボタン または <code>Ctrl+S</code> でプロジェクト全体(.spj)を保存し、自動で <code>verilog_sources/</code> に.vファイルを出力します。<br>
              エディタのタイトルバー右上にあるフロッピーアイコンを押すと、現在開いている単一の.vファイルのみを上書き保存できます。
            </div>
          </div>
        </div>
        <p class="tutorial-note">💡 <code>例</code> ドロップダウンからサンプルプロジェクトを読み込むこともできます。</p>
      `,
    },
    {
      title: "シミュレーションの実行",
      icon: "▶️",
      body: `
        <p>コードを書いたら、シミュレーションを実行しましょう。</p>
        <div class="tutorial-steps-list">
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">1</span>
            <div>
              <strong>トップモジュールの選択</strong><br>
              ツールバーの <code>Top</code> でシミュレーション対象のモジュールを選択します。<br>
              <code>(auto)</code> の場合、*_tp / *_tb が自動で選ばれます。
            </div>
          </div>
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">2</span>
            <div>
              <strong>Run ボタンで実行</strong><br>
              ツールバーの <code>▶ Run</code> ボタン、または <strong>F5</strong> キーでシミュレーションを開始します。
            </div>
          </div>
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">3</span>
            <div>
              <strong>パラメータの調整</strong><br>
              <code>Until</code>（シミュレーション時刻の上限）と <code>MaxEv</code>（最大イベント数）で実行範囲を調整できます。
            </div>
          </div>
        </div>
        <p class="tutorial-note">💡 <code>Elab</code> ボタンを押すと、Run せずにモジュール階層・信号一覧だけを確認できます。</p>
      `,
    },
    {
      title: "結果の確認と波形ビューア",
      icon: "📊",
      body: `
        <p>シミュレーション完了後、結果を多角的に確認できます。</p>
        <div class="tutorial-steps-list">
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">1</span>
            <div>
              <strong>Output（コンソール）</strong><br>
              画面下部の Output パネルに <code>$display</code> の出力やエラーメッセージが表示されます。
            </div>
          </div>
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">2</span>
            <div>
              <strong>Hierarchy タブ</strong><br>
              左パネルの <code>Hierarchy</code> タブでモジュール階層・信号一覧を確認できます。信号をクリックすると波形に追加されます。
            </div>
          </div>
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">3</span>
            <div>
              <strong>波形ビューア (Waveform)</strong><br>
              <code>Waveform</code> ボタンまたは <strong>F6</strong> で波形ウィンドウを開きます。<code>Wave</code> タブで表示する信号を選択・並べ替えできます。
            </div>
          </div>
        </div>
      `,
    },
    {
      title: "エラーが出たときは",
      icon: "⚠️",
      body: `
        <p>本ツールは<strong>開発中</strong>のため、未実装の機能によるエラーや予期せぬ不具合が発生する可能性があります。</p>
        <div class="tutorial-steps-list">
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">1</span>
            <div>
              <strong>まずは AI に聞いてみましょう</strong><br>
              エラーが発生した場合は、<strong>エラー内容をコピー</strong>して、ご自身がお使いの AI アシスタント（ChatGPT、Gemini、Claude など）に質問してみてください。<br>
              <code>Copy err</code> ボタンで直近のエラーをクリップボードにコピーできます。
            </div>
          </div>
          <div class="tutorial-step-item">
            <span class="tutorial-step-num">2</span>
            <div>
              <strong>シミュレータのバグの場合</strong><br>
              AI に聞いても解決しない場合や、シミュレータ自体の不具合（バグ）であると思われる場合は、以下のメールアドレスまでご連絡ください。
            </div>
          </div>
        </div>
        <div class="tutorial-contact">
          <span class="tutorial-contact-label">📧 連絡先:</span>
          <a href="mailto:t230g108@gunma-u.ac.jp" class="tutorial-contact-email">t230g108@gunma-u.ac.jp</a>
        </div>
        <p class="tutorial-note">エラーの内容、実行したコード、再現手順を添えていただけると対応がスムーズです。</p>
      `,
    },
    {
      title: "便利なショートカット",
      icon: "⌨️",
      body: `
        <table class="tutorial-shortcuts">
          <thead><tr><th>操作</th><th>ショートカット</th></tr></thead>
          <tbody>
            <tr><td>シミュレーション実行</td><td><kbd>F5</kbd></td></tr>
            <tr><td>Elaborate（階層更新）</td><td><kbd>Ctrl+L</kbd></td></tr>
            <tr><td>波形ウィンドウ表示</td><td><kbd>F6</kbd></td></tr>
            <tr><td>プロジェクト保存</td><td><kbd>Ctrl+S</kbd></td></tr>
            <tr><td>ファイルを開く</td><td><kbd>Ctrl+O</kbd></td></tr>
            <tr><td>新規プロジェクト</td><td><kbd>Ctrl+N</kbd></td></tr>
            <tr><td>検索</td><td><kbd>Ctrl+F</kbd></td></tr>
            <tr><td>シミュレーション停止</td><td><kbd>Esc</kbd></td></tr>
          </tbody>
        </table>
        <p class="tutorial-note">このチュートリアルは <code>Help → チュートリアルを表示</code> からいつでも再確認できます。</p>
      `,
    },
  ];

  let modalEl = null;
  let currentStep = 0;

  function createModal() {
    if (modalEl) return modalEl;

    const overlay = document.createElement("div");
    overlay.id = "tutorial-overlay";
    overlay.className = "tutorial-overlay";
    overlay.innerHTML = `
      <div class="tutorial-modal" role="dialog" aria-modal="true" aria-labelledby="tutorial-title">
        <div class="tutorial-header">
          <span class="tutorial-icon" id="tutorial-icon"></span>
          <h2 class="tutorial-title" id="tutorial-title"></h2>
          <button type="button" class="tutorial-close" id="tutorial-close" title="閉じる" aria-label="チュートリアルを閉じる">×</button>
        </div>
        <div class="tutorial-body" id="tutorial-body"></div>
        <div class="tutorial-footer">
          <div class="tutorial-progress" id="tutorial-progress"></div>
          <div class="tutorial-nav">
            <button type="button" class="tutorial-btn tutorial-btn-skip" id="tutorial-skip">スキップ</button>
            <div class="tutorial-nav-main">
              <button type="button" class="tutorial-btn tutorial-btn-prev" id="tutorial-prev">← 前へ</button>
              <button type="button" class="tutorial-btn tutorial-btn-next" id="tutorial-next">次へ →</button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    modalEl = overlay;

    // Event listeners
    overlay.querySelector("#tutorial-close").addEventListener("click", close);
    overlay.querySelector("#tutorial-skip").addEventListener("click", close);
    overlay.querySelector("#tutorial-prev").addEventListener("click", () => goTo(currentStep - 1));
    overlay.querySelector("#tutorial-next").addEventListener("click", () => {
      if (currentStep >= STEPS.length - 1) {
        close();
      } else {
        goTo(currentStep + 1);
      }
    });

    // Close on overlay background click
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });

    // Close on Escape
    overlay.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });

    return overlay;
  }

  function renderStep() {
    const step = STEPS[currentStep];
    if (!step || !modalEl) return;

    modalEl.querySelector("#tutorial-icon").textContent = step.icon;
    modalEl.querySelector("#tutorial-title").textContent = step.title;
    modalEl.querySelector("#tutorial-body").innerHTML = step.body;

    // Navigation buttons
    const prevBtn = modalEl.querySelector("#tutorial-prev");
    const nextBtn = modalEl.querySelector("#tutorial-next");
    prevBtn.disabled = currentStep === 0;
    prevBtn.style.visibility = currentStep === 0 ? "hidden" : "visible";

    if (currentStep >= STEPS.length - 1) {
      nextBtn.textContent = "はじめる ✓";
      nextBtn.classList.add("tutorial-btn-finish");
    } else {
      nextBtn.textContent = "次へ →";
      nextBtn.classList.remove("tutorial-btn-finish");
    }

    // Progress dots
    const progress = modalEl.querySelector("#tutorial-progress");
    progress.innerHTML = STEPS.map((_, i) =>
      `<span class="tutorial-dot${i === currentStep ? " active" : ""}" data-step="${i}"></span>`
    ).join("");

    // Click on dot to navigate
    progress.querySelectorAll(".tutorial-dot").forEach((dot) => {
      dot.addEventListener("click", () => goTo(Number(dot.dataset.step)));
    });
  }

  function goTo(step) {
    currentStep = Math.max(0, Math.min(STEPS.length - 1, step));
    renderStep();
  }

  function open() {
    currentStep = 0;
    const overlay = createModal();
    renderStep();
    overlay.classList.add("visible");
    overlay.querySelector("#tutorial-next")?.focus();
  }

  function close() {
    if (modalEl) {
      modalEl.classList.remove("visible");
    }
    markSeen();
  }

  function markSeen() {
    try {
      localStorage.setItem(TUTORIAL_SEEN_KEY, "1");
    } catch { /* private mode */ }
  }

  function hasSeen() {
    try {
      return localStorage.getItem(TUTORIAL_SEEN_KEY) === "1";
    } catch {
      return false;
    }
  }

  /** 初回起動時に自動表示。既に見ていたらスキップ。 */
  function showIfFirstVisit() {
    if (!hasSeen()) {
      // DOMの構築が完了してから少し待って表示
      setTimeout(open, 600);
    }
  }

  /** Help メニューなどから手動で表示 */
  function show() {
    open();
  }

  global.HDLSimTutorial = {
    show,
    showIfFirstVisit,
  };
})(typeof window !== "undefined" ? window : globalThis);
