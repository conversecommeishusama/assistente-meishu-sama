// Aviso de cookies + carregamento condicional do Meta Pixel (2026-08-03).
// O Pixel só é carregado depois que a pessoa aceitar explicitamente -- nunca
// antes, mesmo que a escolha nunca tenha sido feita (padrão: não carregado).
// A escolha (aceito/recusado) fica salva em localStorage e não é perguntada
// de novo. Ver templates/privacidade.html item 2.7/4 para a divulgação
// completa desse cookie.

const COOKIE_CONSENT_KEY = "goshinsho-cookie-consent"; // "accepted" | "rejected"

const COOKIE_CONSENT_TEXT = {
    "Português": { message: "Usamos um cookie de publicidade (Meta Pixel) para medir a eficácia de campanhas — só com sua permissão. Veja detalhes na Política de Privacidade.", accept: "Aceitar", reject: "Recusar", linkText: "Política de Privacidade" },
    "English": { message: "We use an advertising cookie (Meta Pixel) to measure campaign effectiveness — only with your permission. See details in our Privacy Policy.", accept: "Accept", reject: "Decline", linkText: "Privacy Policy" },
    "Español": { message: "Usamos una cookie publicitaria (Meta Pixel) para medir la eficacia de campañas — solo con tu permiso. Consulta los detalles en la Política de Privacidad.", accept: "Aceptar", reject: "Rechazar", linkText: "Política de Privacidad" },
    "日本語": { message: "キャンペーンの効果測定のため、広告用クッキー（Meta Pixel）を使用します — お客様の許可がある場合のみです。詳細はプライバシーポリシーをご覧ください。", accept: "同意する", reject: "拒否する", linkText: "プライバシーポリシー" },
    "中文": { message: "我们使用广告Cookie（Meta Pixel）来衡量广告活动效果——仅在您允许的情况下使用。详情请见隐私政策。", accept: "接受", reject: "拒绝", linkText: "隐私政策" },
    "हिन्दी": { message: "हम अभियानों की प्रभावशीलता मापने के लिए एक विज्ञापन कुकी (Meta Pixel) का उपयोग करते हैं — केवल आपकी अनुमति से। विवरण के लिए गोपनीयता नीति देखें।", accept: "स्वीकार करें", reject: "अस्वीकार करें", linkText: "गोपनीयता नीति" },
    "العربية": { message: "نستخدم ملف تعريف ارتباط إعلاني (Meta Pixel) لقياس فعالية الحملات — فقط بإذنك. راجع التفاصيل في سياسة الخصوصية.", accept: "قبول", reject: "رفض", linkText: "سياسة الخصوصية" },
    "Français": { message: "Nous utilisons un cookie publicitaire (Meta Pixel) pour mesurer l'efficacité des campagnes — uniquement avec votre permission. Voir les détails dans la Politique de Confidentialité.", accept: "Accepter", reject: "Refuser", linkText: "Politique de Confidentialité" },
    "বাংলা": { message: "প্রচারণার কার্যকারিতা পরিমাপ করতে আমরা একটি বিজ্ঞাপন কুকি (Meta Pixel) ব্যবহার করি — শুধুমাত্র আপনার অনুমতিতে। বিস্তারিত জানতে গোপনীয়তা নীতি দেখুন।", accept: "গ্রহণ করুন", reject: "প্রত্যাখ্যান করুন", linkText: "গোপনীয়তা নীতি" },
    "Русский": { message: "Мы используем рекламный файл cookie (Meta Pixel) для измерения эффективности кампаний — только с вашего разрешения. Подробности в Политике конфиденциальности.", accept: "Принять", reject: "Отклонить", linkText: "Политика конфиденциальности" },
    "اردو": { message: "ہم مہمات کی تاثیر ناپنے کے لیے ایک اشتہاری کوکی (Meta Pixel) استعمال کرتے ہیں — صرف آپ کی اجازت سے۔ تفصیلات کے لیے رازداری کی پالیسی دیکھیں۔", accept: "قبول کریں", reject: "مسترد کریں", linkText: "رازداری کی پالیسی" },
    "Indonesia": { message: "Kami menggunakan cookie iklan (Meta Pixel) untuk mengukur efektivitas kampanye — hanya dengan izin Anda. Lihat detail di Kebijakan Privasi.", accept: "Terima", reject: "Tolak", linkText: "Kebijakan Privasi" },
    "Deutsch": { message: "Wir verwenden ein Werbe-Cookie (Meta Pixel), um die Wirksamkeit von Kampagnen zu messen — nur mit Ihrer Erlaubnis. Details finden Sie in der Datenschutzrichtlinie.", accept: "Akzeptieren", reject: "Ablehnen", linkText: "Datenschutzrichtlinie" },
};

function initMetaPixel(pixelId) {
    if (!pixelId || window.__goshinshoPixelLoaded) return;
    window.__goshinshoPixelLoaded = true;
    /* eslint-disable */
    !function(f,b,e,v,n,t,s)
    {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};
    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
    n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s)}(window, document,'script',
    'https://connect.facebook.net/en_US/fbevents.js');
    /* eslint-enable */
    window.fbq("init", pixelId);
    window.fbq("track", "PageView");
}

// Chamado por outros scripts (ex. após cadastro concluído) -- não faz nada
// se o Pixel não estiver carregado (usuário não consentiu ou ainda não
// respondeu ao aviso).
window.goshinshoTrackConversion = function (eventName) {
    if (typeof window.fbq === "function") {
        window.fbq("track", eventName || "CompleteRegistration");
    }
};

function showCookieBanner(pixelId) {
    const language = localStorage.getItem("goshinsho-language") || "Português";
    const t = COOKIE_CONSENT_TEXT[language] || COOKIE_CONSENT_TEXT["Português"];

    const banner = document.createElement("div");
    banner.className = "cookie-consent-banner";
    banner.innerHTML = `
        <p>${t.message}</p>
        <div class="cookie-consent-actions">
            <button type="button" class="cookie-consent-reject">${t.reject}</button>
            <button type="button" class="cookie-consent-accept">${t.accept}</button>
        </div>
    `;
    document.body.appendChild(banner);

    banner.querySelector(".cookie-consent-accept").addEventListener("click", () => {
        localStorage.setItem(COOKIE_CONSENT_KEY, "accepted");
        banner.remove();
        initMetaPixel(pixelId);
    });
    banner.querySelector(".cookie-consent-reject").addEventListener("click", () => {
        localStorage.setItem(COOKIE_CONSENT_KEY, "rejected");
        banner.remove();
    });
}

(function setupCookieConsent() {
    const pixelId = document.body.dataset.metaPixelId;
    if (!pixelId) return; // Pixel não configurado no servidor -- nada a fazer.

    const consent = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (consent === "accepted") {
        initMetaPixel(pixelId);
    } else if (consent !== "rejected") {
        showCookieBanner(pixelId);
    }
})();
