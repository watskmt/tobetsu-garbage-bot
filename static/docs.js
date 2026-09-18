// プライバシーポリシー・利用規約ページ共通: 運営者情報を埋め込む
// （/privacy /terms は CSP でインラインスクリプトが禁止されているため外部ファイルにしている）
async function loadInfo() {
  try {
    const res = await fetch('/api/bot-info');
    const info = await res.json();
    if (info.operator_name) {
      const el = document.getElementById('operator-name');
      if (el) el.textContent = info.operator_name;
      document.querySelectorAll('.operator-name-ref').forEach(el => el.textContent = info.operator_name);
    }

    const contact = document.getElementById('contact-info');
    if (contact) {
      contact.textContent = '';
      const name = document.createElement('p');
      name.className = 'font-medium mb-1';
      name.textContent = info.operator_name || '当別町ごみ収集日Bot運営者';
      contact.appendChild(name);

      const line = document.createElement('p');
      if (info.operator_email) {
        line.textContent = 'メール: ';
        const a = document.createElement('a');
        a.href = 'mailto:' + info.operator_email;
        a.className = 'text-blue-500';
        a.textContent = info.operator_email;
        line.appendChild(a);
      } else {
        line.className = 'text-gray-500';
        line.textContent = 'お問い合わせは本サービスの LINE トーク画面よりご連絡ください。';
      }
      contact.appendChild(line);
    }
  } catch (e) {}

  const year = document.getElementById('copyright-year');
  if (year) year.textContent = new Date().getFullYear();
}
loadInfo();
