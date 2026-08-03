const sidebar = document.querySelector("#sidebar");
const overlay = document.querySelector("#overlay");
const menuButton = document.querySelector("#menu-button");
const chat = document.querySelector("#chat");
const chatForm = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message-input");
const languageInput = document.querySelector("#language");
const languageButton = document.querySelector("#language-button");
const languageDialog = document.querySelector("#language-dialog");
const languageOptions = document.querySelector("#language-options");
const languageConfirm = document.querySelector("#language-confirm");
const languageCancel = document.querySelector("#language-cancel");
const newChatButton = document.querySelector("#new-chat-button");
const quotaTitle = document.querySelector("#quota-title");
const quotaMessage = document.querySelector("#quota-message");
const quotaSignupHint = document.querySelector("#quota-signup-hint");
const quotaSignupButton = document.querySelector("#quota-signup-button");
const quotaCard = document.querySelector("#quota-card");
const historySearch = document.querySelector("#history-search");
const favoritesList = document.querySelector("#favorites-list");
const resetPasswordPanel = document.querySelector("#reset-password-panel");
const resetPasswordMessage = document.querySelector("#reset-password-message");
const supportPanel = document.querySelector("#contact-panel");
const supportMessage = document.querySelector("#support-message");
const supportTicketList = document.querySelector("#support-ticket-list");
const supportTicketDetail = document.querySelector("#support-ticket-detail");
const supportTicketThread = document.querySelector("#support-ticket-thread");
const supportReplyInput = document.querySelector("#support-reply-input");
const supportReplyButton = document.querySelector("#support-reply-button");
const premiumGrantPanel = document.querySelector("#premium-grant-panel");
const premiumGrantMessage = document.querySelector("#premium-grant-message");
const subscriptionIntroDialog = document.querySelector("#subscription-intro-dialog");
const subscriptionIntroConfirm = document.querySelector("#subscription-intro-confirm");
const subscriptionIntroGrant = document.querySelector("#subscription-intro-grant");
const quotaPricingNote = document.querySelector("#quota-pricing-note");
const isLoggedIn = document.body.dataset.loggedIn === "true";
const subscriptionIntroStorageKey = "goshinsho-subscription-intro-seen";

const languageStorageKey = "goshinsho-language";
const favoritesStorageKey = "goshinsho-favorites";
const languageLabels = {
    "Português": "Idioma: Português",
    "English": "Language: English",
    "Español": "Idioma: Español",
    "日本語": "言語: 日本語",
    "中文": "语言: 中文",
    "हिन्दी": "भाषा: हिन्दी",
    "العربية": "اللغة: العربية",
    "Français": "Langue : Français",
    "বাংলা": "ভাষা: বাংলা",
    "Русский": "Язык: Русский",
    "اردو": "زبان: اردو",
    "Indonesia": "Bahasa: Indonesia",
    "Deutsch": "Sprache: Deutsch",
};

const uiTranslations = {
    "Português": {
        quotaRequiredTitle: "Cadastro necessário",
        quotaRequiredMessage:
            "Crie sua conta gratuita para fazer perguntas -- o acesso é premium gratuito, com perguntas ilimitadas, sem necessidade de assinatura paga.",
        menu: "Menu",
        history: "Histórico",
        newChat: "+ Nova conversa",
        conversations: "Conversas",
        historySearch: "Buscar no histórico...",
        noHistory: "Nenhuma conversa salva ainda.",
        loginHistory: "Faça login para ver seu histórico.",
        favorites: "Favoritos",
        historyAria: "Abrir histórico",
        subscribe: "Apoiar ❤",
        logout: "Sair",
        login: "Login",
        register: "Cadastro",
        contact: "Contato",
        loginTitle: "Acesse sua conta",
        password: "Senha",
        rememberMe: "Mantenha-me conectado",
        signIn: "Entrar",
        forgotPassword: "Esqueci minha senha",
        registerTitle: "Criar cadastro",
        registerPolicyNote: "Cadastro gratuito: acesso premium para sempre, com perguntas ilimitadas. Sem necessidade de assinatura paga.",
        confirmPassword: "Confirmar senha",
        createAccount: "Cadastrar",
        humanCheck: "Sou humano",
        resetTitle: "Recuperar senha",
        resetNote: "Digite seu e-mail cadastrado para receber um link de redefinição de senha.",
        recoveryButton: "Enviar link de recuperação",
        backToChat: "Voltar ao chat",
        newPasswordTitle: "Nova senha",
        newPasswordNote: "Digite e confirme sua nova senha.",
        newPasswordPlaceholder: "Nova senha",
        confirmNewPassword: "Confirmar nova senha",
        updatePassword: "Atualizar senha",
        contactTitle: "Suporte",
        name: "Nome",
        messageLabel: "Mensagem",
        send: "Enviar",
        loginHint: "Para fazer perguntas, crie sua conta ou faça login.",
        quotaSignupHint: "Crie sua conta gratuita para fazer perguntas.",
        heroTitle: "Como posso ajudar?",
        heroSubtitle: "Faça uma pergunta sobre os escritos de Meishu-Sama.",
        chatPlaceholder: "Digite sua pergunta...",
        freeAccount: "Criar conta gratuita",
        quotaPricingText: "O Goshinsho é gratuito para todos. Cada pergunta usa inteligência artificial e servidores em nuvem, que têm custo real de operação — se o app te ajuda, considere apoiar com uma doação voluntária.",
        makeDonation: "Fazer uma doação",
        subscriptionIntroEyebrow: "Sobre o Goshinsho",
        subscriptionIntroTitle: "O Goshinsho é gratuito para todos",
        subscriptionIntroText: "Cada pergunta no Goshinsho usa inteligência artificial e servidores em nuvem, que têm custo real de operação. Doações voluntárias ajudam a manter o aplicativo disponível e a melhorar as respostas.",
        subscriptionIntroConfirm: "Entendi",
        languageTitle: "Escolha o idioma do aplicativo",
        languageNote: "O site será ajustado para o idioma escolhido e sua preferência ficará salva neste dispositivo.",
        back: "Voltar",
        continue: "Continuar",
        loading: "Consultando os escritos...",
        checkingJapanese:
            "Não encontrei uma resposta adequada nos textos traduzidos. Estou consultando o original em japonês — isso pode levar até 2 minutos.",
        sourcesTitle: "Fontes identificadas",
        noSources: "As fontes aparecem citadas diretamente no corpo da resposta.",
        like: "Gostei",
        dislike: "Não gostei",
        favorite: "Salvar favorito",
        showSources: "Ver fontes",
        citationModeDirect: "Direta",
        citationModeCited: "Com citações",
        citationModeAria: "Formato da resposta",
        citeSources: "Refazer com citações",
        citingSources: "Refazendo com citações...",
        share: "Compartilhar",
        shareCopyLink: "Copiar link",
        shareWhatsapp: "WhatsApp",
        shareEmail: "E-mail",
        shareCopied: "Copiado",
        shareError: "Erro",
    },
    "English": {
        quotaRequiredTitle: "Registration required",
        quotaRequiredMessage:
            "Create your free account to ask questions -- access is free premium, with unlimited questions, no paid subscription needed.",
        menu: "Menu",
        history: "History",
        newChat: "+ New chat",
        conversations: "Conversations",
        historySearch: "Search history...",
        noHistory: "No saved conversations yet.",
        loginHistory: "Sign in to see your history.",
        favorites: "Favorites",
        historyAria: "Open history",
        subscribe: "Support ❤",
        logout: "Sign out",
        login: "Login",
        register: "Sign up",
        contact: "Contact",
        loginTitle: "Access your account",
        password: "Password",
        rememberMe: "Keep me signed in",
        signIn: "Sign in",
        forgotPassword: "Forgot password",
        registerTitle: "Create account",
        registerPolicyNote: "Free signup: premium access forever, with unlimited questions. No paid subscription needed.",
        confirmPassword: "Confirm password",
        createAccount: "Create account",
        humanCheck: "I am human",
        resetTitle: "Reset password",
        resetNote: "Enter your registered email to receive a password reset link.",
        recoveryButton: "Send recovery link",
        backToChat: "Back to chat",
        newPasswordTitle: "New password",
        newPasswordNote: "Enter and confirm your new password.",
        newPasswordPlaceholder: "New password",
        confirmNewPassword: "Confirm new password",
        updatePassword: "Update password",
        contactTitle: "Support",
        name: "Name",
        messageLabel: "Message",
        send: "Send",
        loginHint: "Create an account or sign in to ask questions.",
        quotaSignupHint: "Create your free account to ask questions.",
        heroTitle: "How can I help?",
        heroSubtitle: "Ask a question about Meishu-Sama's writings.",
        chatPlaceholder: "Type your question...",
        freeAccount: "Create free account",
        quotaPricingText: "Goshinsho is free for everyone. Each question uses artificial intelligence and cloud servers, which have a real operating cost — if the app helps you, consider supporting it with a voluntary donation.",
        makeDonation: "Make a donation",
        subscriptionIntroEyebrow: "About Goshinsho",
        subscriptionIntroTitle: "Goshinsho is free for everyone",
        subscriptionIntroText: "Each question on Goshinsho uses artificial intelligence and cloud servers, which have a real operating cost. Voluntary donations help keep the app available and improve the answers.",
        subscriptionIntroConfirm: "Got it",
        languageTitle: "Choose the app language",
        languageNote: "The site will adjust to the chosen language and save your preference on this device.",
        back: "Back",
        continue: "Continue",
        loading: "Consulting the writings...",
        checkingJapanese:
            "I didn't find an adequate answer in the translated texts. I'm checking the original Japanese — this may take up to 2 minutes.",
        sourcesTitle: "Identified sources",
        noSources: "Sources appear in the answer body when the in-depth response finds matching excerpts.",
        like: "Like",
        dislike: "Dislike",
        favorite: "Save favorite",
        showSources: "View sources",
        citationModeDirect: "Direct",
        citationModeCited: "With citations",
        citationModeAria: "Response format",
        citeSources: "Redo with citations",
        citingSources: "Redoing with citations...",
        share: "Share",
        shareCopyLink: "Copy link",
        shareWhatsapp: "WhatsApp",
        shareEmail: "Email",
        shareCopied: "Copied",
        shareError: "Error",
    },
    "Español": {
        quotaRequiredTitle: "Registro necesario",
        quotaRequiredMessage:
            "Crea tu cuenta gratuita para hacer preguntas -- el acceso es premium gratuito, con preguntas ilimitadas, sin necesidad de suscripción paga.",
        menu: "Menú",
        history: "Historial",
        newChat: "+ Nueva conversación",
        conversations: "Conversaciones",
        historySearch: "Buscar en el historial...",
        noHistory: "Aún no hay conversaciones guardadas.",
        loginHistory: "Inicia sesión para ver tu historial.",
        favorites: "Favoritos",
        historyAria: "Abrir historial",
        subscribe: "Apoyar ❤",
        logout: "Salir",
        login: "Login",
        register: "Registro",
        contact: "Contacto",
        loginTitle: "Accede a tu cuenta",
        password: "Contraseña",
        rememberMe: "Mantener sesión iniciada",
        signIn: "Entrar",
        forgotPassword: "Olvidé mi contraseña",
        registerTitle: "Crear cuenta",
        registerPolicyNote: "Registro gratis: acceso premium para siempre, con preguntas ilimitadas. Sin necesidad de suscripción paga.",
        confirmPassword: "Confirmar contraseña",
        createAccount: "Registrarse",
        humanCheck: "Soy humano",
        resetTitle: "Recuperar contraseña",
        resetNote: "Ingresa tu email registrado para recibir un enlace de recuperación.",
        recoveryButton: "Enviar enlace de recuperación",
        backToChat: "Volver al chat",
        newPasswordTitle: "Nueva contraseña",
        newPasswordNote: "Ingresa y confirma tu nueva contraseña.",
        newPasswordPlaceholder: "Nueva contraseña",
        confirmNewPassword: "Confirmar nueva contraseña",
        updatePassword: "Actualizar contraseña",
        contactTitle: "Soporte",
        name: "Nombre",
        messageLabel: "Mensaje",
        send: "Enviar",
        loginHint: "Crea una cuenta o inicia sesión para hacer preguntas.",
        quotaSignupHint: "Crea tu cuenta gratuita para hacer preguntas.",
        heroTitle: "¿Cómo puedo ayudar?",
        heroSubtitle: "Haz una pregunta sobre los escritos de Meishu-Sama.",
        chatPlaceholder: "Escribe tu pregunta...",
        freeAccount: "Crear cuenta gratuita",
        quotaPricingText: "Goshinsho es gratuito para todos. Cada pregunta usa inteligencia artificial y servidores en la nube, que tienen un costo real de operación — si la app te ayuda, considera apoyarla con una donación voluntaria.",
        makeDonation: "Hacer una donación",
        subscriptionIntroEyebrow: "Sobre Goshinsho",
        subscriptionIntroTitle: "Goshinsho es gratuito para todos",
        subscriptionIntroText: "Cada pregunta en Goshinsho usa inteligencia artificial y servidores en la nube, que tienen un costo real de operación. Las donaciones voluntarias ayudan a mantener la app disponible y a mejorar las respuestas.",
        subscriptionIntroConfirm: "Entendido",
        languageTitle: "Elige el idioma de la aplicación",
        languageNote: "El sitio se ajustará al idioma elegido y guardará tu preferencia en este dispositivo.",
        back: "Volver",
        continue: "Continuar",
        loading: "Consultando los escritos...",
        checkingJapanese:
            "No encontré una respuesta adecuada en los textos traducidos. Estoy consultando el original en japonés — esto puede tardar hasta 2 minutos.",
        sourcesTitle: "Fuentes identificadas",
        noSources: "Las fuentes aparecen en el cuerpo de la respuesta cuando la respuesta aprofundizada encuentra fragmentos correspondientes.",
        like: "Me gusta",
        dislike: "No me gusta",
        favorite: "Guardar favorito",
        showSources: "Ver fuentes",
        citationModeDirect: "Directa",
        citationModeCited: "Con citas",
        citationModeAria: "Formato de la respuesta",
        citeSources: "Rehacer con citas",
        citingSources: "Rehaciendo con citas...",
        share: "Compartir",
        shareCopyLink: "Copiar enlace",
        shareWhatsapp: "WhatsApp",
        shareEmail: "Correo",
        shareCopied: "Copiado",
        shareError: "Error",
    },
    "日本語": {
        quotaRequiredTitle: "登録が必要です",
        quotaRequiredMessage:
            "質問するには無料アカウントを作成してください -- 無料プレミアムアクセスで、質問回数は無制限、有料プランへの登録は不要です。",
        menu: "メニュー",
        history: "履歴",
        newChat: "+ 新しい会話",
        conversations: "会話",
        historySearch: "履歴を検索...",
        noHistory: "保存された会話はまだありません。",
        loginHistory: "履歴を見るにはログインしてください。",
        favorites: "お気に入り",
        historyAria: "履歴を開く",
        subscribe: "支援する ❤",
        logout: "ログアウト",
        login: "ログイン",
        register: "新規登録",
        contact: "お問い合わせ",
        loginTitle: "アカウントにアクセス",
        password: "パスワード",
        rememberMe: "ログイン状態を保持する",
        signIn: "ログイン",
        forgotPassword: "パスワードをお忘れですか",
        registerTitle: "アカウントを作成",
        registerPolicyNote: "無料登録：永久にプレミアムアクセス、質問回数は無制限。有料プランへの登録は不要です。",
        confirmPassword: "パスワードの確認",
        createAccount: "登録する",
        humanCheck: "私は人間です",
        resetTitle: "パスワードの再設定",
        resetNote: "登録済みのメールアドレスを入力すると、パスワード再設定リンクが届きます。",
        recoveryButton: "再設定リンクを送信",
        backToChat: "チャットに戻る",
        newPasswordTitle: "新しいパスワード",
        newPasswordNote: "新しいパスワードを入力して確認してください。",
        newPasswordPlaceholder: "新しいパスワード",
        confirmNewPassword: "新しいパスワードの確認",
        updatePassword: "パスワードを更新",
        contactTitle: "サポート",
        name: "お名前",
        messageLabel: "メッセージ",
        send: "送信",
        loginHint: "質問するにはアカウントを作成するかログインしてください。",
        quotaSignupHint: "質問するには無料アカウントを作成してください。",
        heroTitle: "何をお手伝いしましょうか？",
        heroSubtitle: "明主様の教えについて質問してください。",
        chatPlaceholder: "ご質問を入力してください...",
        freeAccount: "無料アカウントを作成",
        quotaPricingText: "Goshinshoはすべての人に無料です。各質問は人工知能とクラウドサーバーを使用しており、実際の運用コストがかかります — アプリが役立っていると感じたら、任意の寄付でのご支援をご検討ください。",
        makeDonation: "寄付する",
        subscriptionIntroEyebrow: "Goshinshoについて",
        subscriptionIntroTitle: "Goshinshoはすべての人に無料です",
        subscriptionIntroText: "Goshinshoでの各質問は人工知能とクラウドサーバーを使用しており、実際の運用コストがかかります。任意の寄付はアプリの提供継続と回答の改善に役立ちます。",
        subscriptionIntroConfirm: "了解しました",
        languageTitle: "アプリの言語を選択",
        languageNote: "サイトは選択された言語に切り替わり、この端末に設定が保存されます。",
        back: "戻る",
        continue: "続ける",
        loading: "教えを確認しています...",
        checkingJapanese: "翻訳されたテキストでは適切な回答が見つかりませんでした。日本語の原文を確認しています — 最大2分ほどかかる場合があります。",
        sourcesTitle: "特定された出典",
        noSources: "詳細回答で該当箇所が見つかった場合、出典が回答本文に表示されます。",
        like: "いいね",
        dislike: "よくない",
        favorite: "お気に入りに保存",
        showSources: "出典を見る",
        citationModeDirect: "直接",
        citationModeCited: "引用付き",
        citationModeAria: "回答形式",
        citeSources: "引用付きでやり直す",
        citingSources: "引用付きでやり直しています...",
        share: "共有",
        shareCopyLink: "リンクをコピー",
        shareWhatsapp: "WhatsApp",
        shareEmail: "メール",
        shareCopied: "コピーしました",
        shareError: "エラー",
    },
    "中文": {
        quotaRequiredTitle: "需要注册",
        quotaRequiredMessage:
            "创建您的免费账户以开始提问 -- 免费获得高级权限，无限提问，无需付费订阅。",
        menu: "菜单",
        history: "历史记录",
        newChat: "+ 新对话",
        conversations: "对话",
        historySearch: "搜索历史记录...",
        noHistory: "暂无已保存的对话。",
        loginHistory: "登录后可查看您的历史记录。",
        favorites: "收藏",
        historyAria: "打开历史记录",
        subscribe: "支持 ❤",
        logout: "退出登录",
        login: "登录",
        register: "注册",
        contact: "联系我们",
        loginTitle: "登录您的账户",
        password: "密码",
        rememberMe: "保持登录状态",
        signIn: "登录",
        forgotPassword: "忘记密码",
        registerTitle: "创建账户",
        registerPolicyNote: "免费注册：永久获得高级权限，无限提问。无需付费订阅。",
        confirmPassword: "确认密码",
        createAccount: "注册",
        humanCheck: "我是真人",
        resetTitle: "重置密码",
        resetNote: "输入您注册时使用的邮箱以接收密码重置链接。",
        recoveryButton: "发送重置链接",
        backToChat: "返回聊天",
        newPasswordTitle: "新密码",
        newPasswordNote: "请输入并确认您的新密码。",
        newPasswordPlaceholder: "新密码",
        confirmNewPassword: "确认新密码",
        updatePassword: "更新密码",
        contactTitle: "支持",
        name: "姓名",
        messageLabel: "留言",
        send: "发送",
        loginHint: "请注册账户或登录后提问。",
        quotaSignupHint: "创建您的免费账户以开始提问。",
        heroTitle: "我能帮您什么？",
        heroSubtitle: "就明主様的教诲提出问题。",
        chatPlaceholder: "请输入您的问题...",
        freeAccount: "创建免费账户",
        quotaPricingText: "Goshinsho对所有人免费开放。每个问题都会使用人工智能和云服务器，这些都有实际的运营成本——如果这个应用对你有帮助，欢迎通过自愿捐赠来支持我们。",
        makeDonation: "进行捐赠",
        subscriptionIntroEyebrow: "关于Goshinsho",
        subscriptionIntroTitle: "Goshinsho对所有人免费开放",
        subscriptionIntroText: "Goshinsho上的每个问题都会使用人工智能和云服务器，这些都有实际的运营成本。自愿捐赠有助于维持应用的可用性并改进回答质量。",
        subscriptionIntroConfirm: "知道了",
        languageTitle: "选择应用语言",
        languageNote: "网站将切换为所选语言，并在此设备上保存您的偏好设置。",
        back: "返回",
        continue: "继续",
        loading: "正在查阅教诲...",
        checkingJapanese: "未能在译文中找到合适的答案。正在查阅日文原文——这可能需要长达2分钟。",
        sourcesTitle: "已识别的来源",
        noSources: "当深入回答找到匹配片段时，来源会显示在回答正文中。",
        like: "赞",
        dislike: "踩",
        favorite: "收藏",
        showSources: "查看来源",
        citationModeDirect: "直接",
        citationModeCited: "附引用",
        citationModeAria: "回答格式",
        citeSources: "附引用重新回答",
        citingSources: "正在附引用重新回答...",
        share: "分享",
        shareCopyLink: "复制链接",
        shareWhatsapp: "WhatsApp",
        shareEmail: "邮件",
        shareCopied: "已复制",
        shareError: "出错了",
    },
    "हिन्दी": {
        quotaRequiredTitle: "पंजीकरण आवश्यक है",
        quotaRequiredMessage:
            "सवाल पूछने के लिए अपना निःशुल्क खाता बनाएं -- यह मुफ़्त प्रीमियम एक्सेस है, असीमित सवाल, किसी सशुल्क सदस्यता की ज़रूरत नहीं।",
        menu: "मेनू",
        history: "इतिहास",
        newChat: "+ नई बातचीत",
        conversations: "बातचीत",
        historySearch: "इतिहास में खोजें...",
        noHistory: "अभी तक कोई सहेजी गई बातचीत नहीं है।",
        loginHistory: "अपना इतिहास देखने के लिए लॉगिन करें।",
        favorites: "पसंदीदा",
        historyAria: "इतिहास खोलें",
        subscribe: "सहयोग करें ❤",
        logout: "लॉगआउट",
        login: "लॉगिन",
        register: "पंजीकरण करें",
        contact: "संपर्क करें",
        loginTitle: "अपने खाते में प्रवेश करें",
        password: "पासवर्ड",
        rememberMe: "मुझे लॉगिन रखें",
        signIn: "साइन इन करें",
        forgotPassword: "पासवर्ड भूल गए",
        registerTitle: "खाता बनाएं",
        registerPolicyNote: "निःशुल्क पंजीकरण: हमेशा के लिए प्रीमियम एक्सेस, असीमित सवाल। किसी सशुल्क सदस्यता की ज़रूरत नहीं।",
        confirmPassword: "पासवर्ड की पुष्टि करें",
        createAccount: "खाता बनाएं",
        humanCheck: "मैं इंसान हूं",
        resetTitle: "पासवर्ड रीसेट करें",
        resetNote: "पासवर्ड रीसेट लिंक प्राप्त करने के लिए अपना पंजीकृत ईमेल दर्ज करें।",
        recoveryButton: "रिकवरी लिंक भेजें",
        backToChat: "चैट पर वापस जाएं",
        newPasswordTitle: "नया पासवर्ड",
        newPasswordNote: "अपना नया पासवर्ड दर्ज करें और पुष्टि करें।",
        newPasswordPlaceholder: "नया पासवर्ड",
        confirmNewPassword: "नए पासवर्ड की पुष्टि करें",
        updatePassword: "पासवर्ड अपडेट करें",
        contactTitle: "सहायता",
        name: "नाम",
        messageLabel: "संदेश",
        send: "भेजें",
        loginHint: "सवाल पूछने के लिए खाता बनाएं या लॉगिन करें।",
        quotaSignupHint: "सवाल पूछने के लिए अपना निःशुल्क खाता बनाएं।",
        heroTitle: "मैं आपकी कैसे मदद कर सकता हूं?",
        heroSubtitle: "मेइशु-सामा की शिक्षाओं के बारे में सवाल पूछें।",
        chatPlaceholder: "अपना सवाल लिखें...",
        freeAccount: "निःशुल्क खाता बनाएं",
        quotaPricingText: "Goshinsho सभी के लिए मुफ़्त है। हर सवाल के लिए आर्टिफ़िशियल इंटेलिजेंस और क्लाउड सर्वर का उपयोग होता है, जिनकी वास्तविक परिचालन लागत होती है — अगर यह ऐप आपके लिए उपयोगी है, तो स्वैच्छिक दान देकर सहयोग करने पर विचार करें।",
        makeDonation: "दान करें",
        subscriptionIntroEyebrow: "Goshinsho के बारे में",
        subscriptionIntroTitle: "Goshinsho सभी के लिए मुफ़्त है",
        subscriptionIntroText: "Goshinsho पर हर सवाल के लिए आर्टिफ़िशियल इंटेलिजेंस और क्लाउड सर्वर का उपयोग होता है, जिनकी वास्तविक परिचालन लागत होती है। स्वैच्छिक दान ऐप को उपलब्ध रखने और जवाबों को बेहतर बनाने में मदद करते हैं।",
        subscriptionIntroConfirm: "समझ गया",
        languageTitle: "ऐप की भाषा चुनें",
        languageNote: "साइट चुनी गई भाषा में समायोजित हो जाएगी और आपकी पसंद इस डिवाइस पर सहेजी जाएगी।",
        back: "वापस",
        continue: "जारी रखें",
        loading: "शिक्षाओं की जांच की जा रही है...",
        checkingJapanese: "अनुवादित पाठ में उचित उत्तर नहीं मिला। मूल जापानी पाठ की जांच की जा रही है — इसमें 2 मिनट तक लग सकते हैं।",
        sourcesTitle: "पहचाने गए स्रोत",
        noSources: "जब विस्तृत उत्तर में मिलते-जुलते अंश मिलते हैं, तो स्रोत उत्तर के मुख्य भाग में दिखाई देते हैं।",
        like: "पसंद",
        dislike: "नापसंद",
        favorite: "पसंदीदा में सहेजें",
        showSources: "स्रोत देखें",
        citationModeDirect: "सीधा",
        citationModeCited: "उद्धरण सहित",
        citationModeAria: "उत्तर प्रारूप",
        citeSources: "उद्धरण सहित दोबारा करें",
        citingSources: "उद्धरण सहित दोबारा किया जा रहा है...",
        share: "साझा करें",
        shareCopyLink: "लिंक कॉपी करें",
        shareWhatsapp: "WhatsApp",
        shareEmail: "ईमेल",
        shareCopied: "कॉपी हो गया",
        shareError: "त्रुटि",
    },
    "العربية": {
        quotaRequiredTitle: "التسجيل مطلوب",
        quotaRequiredMessage:
            "أنشئ حسابك المجاني لطرح الأسئلة -- الوصول مجاني ومميز، مع أسئلة غير محدودة، دون الحاجة إلى اشتراك مدفوع.",
        menu: "القائمة",
        history: "السجل",
        newChat: "+ محادثة جديدة",
        conversations: "المحادثات",
        historySearch: "البحث في السجل...",
        noHistory: "لا توجد محادثات محفوظة بعد.",
        loginHistory: "سجّل الدخول لعرض سجلّك.",
        favorites: "المفضلة",
        historyAria: "فتح السجل",
        subscribe: "ادعم ❤",
        logout: "تسجيل الخروج",
        login: "تسجيل الدخول",
        register: "إنشاء حساب",
        contact: "اتصل بنا",
        loginTitle: "الوصول إلى حسابك",
        password: "كلمة المرور",
        rememberMe: "إبقني مسجّل الدخول",
        signIn: "دخول",
        forgotPassword: "نسيت كلمة المرور",
        registerTitle: "إنشاء حساب",
        registerPolicyNote: "تسجيل مجاني: وصول مميز إلى الأبد، مع أسئلة غير محدودة. دون الحاجة إلى اشتراك مدفوع.",
        confirmPassword: "تأكيد كلمة المرور",
        createAccount: "إنشاء حساب",
        humanCheck: "أنا لست روبوتًا",
        resetTitle: "إعادة تعيين كلمة المرور",
        resetNote: "أدخل بريدك الإلكتروني المسجَّل لتلقّي رابط إعادة تعيين كلمة المرور.",
        recoveryButton: "إرسال رابط الاستعادة",
        backToChat: "العودة إلى المحادثة",
        newPasswordTitle: "كلمة مرور جديدة",
        newPasswordNote: "أدخل كلمة المرور الجديدة وأكّدها.",
        newPasswordPlaceholder: "كلمة مرور جديدة",
        confirmNewPassword: "تأكيد كلمة المرور الجديدة",
        updatePassword: "تحديث كلمة المرور",
        contactTitle: "الدعم",
        name: "الاسم",
        messageLabel: "الرسالة",
        send: "إرسال",
        loginHint: "لطرح الأسئلة، أنشئ حسابًا أو سجّل الدخول.",
        quotaSignupHint: "أنشئ حسابك المجاني لطرح الأسئلة.",
        heroTitle: "كيف يمكنني المساعدة؟",
        heroSubtitle: "اطرح سؤالاً عن تعاليم مايشو-ساما.",
        chatPlaceholder: "اكتب سؤالك...",
        freeAccount: "إنشاء حساب مجاني",
        quotaPricingText: "غوشينشو مجاني للجميع. كل سؤال يستخدم الذكاء الاصطناعي وخوادم سحابية، ولها تكلفة تشغيل حقيقية — إذا كان التطبيق يساعدك، ففكّر في دعمه بتبرع تطوعي.",
        makeDonation: "تقديم تبرع",
        subscriptionIntroEyebrow: "عن غوشينشو",
        subscriptionIntroTitle: "غوشينشو مجاني للجميع",
        subscriptionIntroText: "كل سؤال في غوشينشو يستخدم الذكاء الاصطناعي وخوادم سحابية، ولها تكلفة تشغيل حقيقية. التبرعات التطوعية تساعد في إبقاء التطبيق متاحًا وتحسين الإجابات.",
        subscriptionIntroConfirm: "فهمت",
        languageTitle: "اختر لغة التطبيق",
        languageNote: "سيتم ضبط الموقع باللغة المختارة وسيُحفظ تفضيلك على هذا الجهاز.",
        back: "رجوع",
        continue: "متابعة",
        loading: "جارٍ الاطّلاع على التعاليم...",
        checkingJapanese: "لم أجد إجابة مناسبة في النصوص المترجمة. أتحقّق الآن من الأصل الياباني — قد يستغرق ذلك حتى دقيقتين.",
        sourcesTitle: "المصادر المحدَّدة",
        noSources: "تظهر المصادر ضمن نص الإجابة عندما تجد الإجابة المتعمّقة مقاطع مطابقة.",
        like: "إعجاب",
        dislike: "عدم إعجاب",
        favorite: "حفظ في المفضلة",
        showSources: "عرض المصادر",
        citationModeDirect: "مباشر",
        citationModeCited: "مع الاقتباسات",
        citationModeAria: "تنسيق الرد",
        citeSources: "إعادة مع الاقتباسات",
        citingSources: "جارٍ الإعادة مع الاقتباسات...",
        share: "مشاركة",
        shareCopyLink: "نسخ الرابط",
        shareWhatsapp: "واتساب",
        shareEmail: "البريد الإلكتروني",
        shareCopied: "تم النسخ",
        shareError: "خطأ",
    },
    "Français": {
        quotaRequiredTitle: "Inscription requise",
        quotaRequiredMessage:
            "Créez votre compte gratuit pour poser des questions -- l'accès est premium gratuit, avec des questions illimitées, sans besoin d'abonnement payant.",
        menu: "Menu",
        history: "Historique",
        newChat: "+ Nouvelle conversation",
        conversations: "Conversations",
        historySearch: "Rechercher dans l'historique...",
        noHistory: "Aucune conversation enregistrée pour le moment.",
        loginHistory: "Connectez-vous pour voir votre historique.",
        favorites: "Favoris",
        historyAria: "Ouvrir l'historique",
        subscribe: "Soutenir ❤",
        logout: "Se déconnecter",
        login: "Connexion",
        register: "Inscription",
        contact: "Contact",
        loginTitle: "Accédez à votre compte",
        password: "Mot de passe",
        rememberMe: "Rester connecté",
        signIn: "Entrer",
        forgotPassword: "Mot de passe oublié",
        registerTitle: "Créer un compte",
        registerPolicyNote: "Inscription gratuite : accès premium à vie, avec des questions illimitées. Sans besoin d'abonnement payant.",
        confirmPassword: "Confirmer le mot de passe",
        createAccount: "Créer le compte",
        humanCheck: "Je suis humain",
        resetTitle: "Réinitialiser le mot de passe",
        resetNote: "Saisissez votre e-mail enregistré pour recevoir un lien de réinitialisation.",
        recoveryButton: "Envoyer le lien de récupération",
        backToChat: "Retour au chat",
        newPasswordTitle: "Nouveau mot de passe",
        newPasswordNote: "Saisissez et confirmez votre nouveau mot de passe.",
        newPasswordPlaceholder: "Nouveau mot de passe",
        confirmNewPassword: "Confirmer le nouveau mot de passe",
        updatePassword: "Mettre à jour le mot de passe",
        contactTitle: "Support",
        name: "Nom",
        messageLabel: "Message",
        send: "Envoyer",
        loginHint: "Créez un compte ou connectez-vous pour poser des questions.",
        quotaSignupHint: "Créez votre compte gratuit pour poser des questions.",
        heroTitle: "Comment puis-je aider ?",
        heroSubtitle: "Posez une question sur les écrits de Meishu-Sama.",
        chatPlaceholder: "Saisissez votre question...",
        freeAccount: "Créer un compte gratuit",
        quotaPricingText: "Goshinsho est gratuit pour tous. Chaque question utilise l'intelligence artificielle et des serveurs cloud, qui ont un coût de fonctionnement réel — si l'application vous aide, envisagez de la soutenir avec un don volontaire.",
        makeDonation: "Faire un don",
        subscriptionIntroEyebrow: "À propos de Goshinsho",
        subscriptionIntroTitle: "Goshinsho est gratuit pour tous",
        subscriptionIntroText: "Chaque question sur Goshinsho utilise l'intelligence artificielle et des serveurs cloud, qui ont un coût de fonctionnement réel. Les dons volontaires aident à maintenir l'application disponible et à améliorer les réponses.",
        subscriptionIntroConfirm: "Compris",
        languageTitle: "Choisissez la langue de l'application",
        languageNote: "Le site s'adaptera à la langue choisie et enregistrera votre préférence sur cet appareil.",
        back: "Retour",
        continue: "Continuer",
        loading: "Consultation des écrits...",
        checkingJapanese:
            "Je n'ai pas trouvé de réponse adéquate dans les textes traduits. Je consulte l'original en japonais — cela peut prendre jusqu'à 2 minutes.",
        sourcesTitle: "Sources identifiées",
        noSources: "Les sources apparaissent dans le corps de la réponse lorsque la réponse approfondie trouve des extraits correspondants.",
        like: "J'aime",
        dislike: "Je n'aime pas",
        favorite: "Enregistrer comme favori",
        showSources: "Voir les sources",
        citationModeDirect: "Directe",
        citationModeCited: "Avec citations",
        citationModeAria: "Format de réponse",
        citeSources: "Refaire avec citations",
        citingSources: "Nouvelle tentative avec citations...",
        share: "Partager",
        shareCopyLink: "Copier le lien",
        shareWhatsapp: "WhatsApp",
        shareEmail: "E-mail",
        shareCopied: "Copié",
        shareError: "Erreur",
    },
    "বাংলা": {
        quotaRequiredTitle: "নিবন্ধন প্রয়োজন",
        quotaRequiredMessage:
            "প্রশ্ন করতে আপনার বিনামূল্যে অ্যাকাউন্ট তৈরি করুন -- এটি বিনামূল্যে প্রিমিয়াম অ্যাক্সেস, সীমাহীন প্রশ্ন, কোনো পেইড সাবস্ক্রিপশনের প্রয়োজন নেই।",
        menu: "মেনু",
        history: "ইতিহাস",
        newChat: "+ নতুন কথোপকথন",
        conversations: "কথোপকথন",
        historySearch: "ইতিহাসে খুঁজুন...",
        noHistory: "এখনও কোনো সংরক্ষিত কথোপকথন নেই।",
        loginHistory: "আপনার ইতিহাস দেখতে লগইন করুন।",
        favorites: "পছন্দসই",
        historyAria: "ইতিহাস খুলুন",
        subscribe: "সহায়তা করুন ❤",
        logout: "লগআউট",
        login: "লগইন",
        register: "নিবন্ধন করুন",
        contact: "যোগাযোগ",
        loginTitle: "আপনার অ্যাকাউন্টে প্রবেশ করুন",
        password: "পাসওয়ার্ড",
        rememberMe: "আমাকে লগইন রাখুন",
        signIn: "সাইন ইন",
        forgotPassword: "পাসওয়ার্ড ভুলে গেছেন",
        registerTitle: "অ্যাকাউন্ট তৈরি করুন",
        registerPolicyNote: "বিনামূল্যে নিবন্ধন: চিরকালের জন্য প্রিমিয়াম অ্যাক্সেস, সীমাহীন প্রশ্ন। কোনো পেইড সাবস্ক্রিপশনের প্রয়োজন নেই।",
        confirmPassword: "পাসওয়ার্ড নিশ্চিত করুন",
        createAccount: "অ্যাকাউন্ট তৈরি করুন",
        humanCheck: "আমি মানুষ",
        resetTitle: "পাসওয়ার্ড রিসেট করুন",
        resetNote: "পাসওয়ার্ড রিসেট লিংক পেতে আপনার নিবন্ধিত ইমেইল লিখুন।",
        recoveryButton: "রিকভারি লিংক পাঠান",
        backToChat: "চ্যাটে ফিরে যান",
        newPasswordTitle: "নতুন পাসওয়ার্ড",
        newPasswordNote: "আপনার নতুন পাসওয়ার্ড লিখুন এবং নিশ্চিত করুন।",
        newPasswordPlaceholder: "নতুন পাসওয়ার্ড",
        confirmNewPassword: "নতুন পাসওয়ার্ড নিশ্চিত করুন",
        updatePassword: "পাসওয়ার্ড আপডেট করুন",
        contactTitle: "সহায়তা",
        name: "নাম",
        messageLabel: "বার্তা",
        send: "পাঠান",
        loginHint: "প্রশ্ন করতে অ্যাকাউন্ট তৈরি করুন বা লগইন করুন।",
        quotaSignupHint: "প্রশ্ন করতে আপনার বিনামূল্যে অ্যাকাউন্ট তৈরি করুন।",
        heroTitle: "আমি কীভাবে সাহায্য করতে পারি?",
        heroSubtitle: "মেইশু-সামার শিক্ষা সম্পর্কে প্রশ্ন করুন।",
        chatPlaceholder: "আপনার প্রশ্ন লিখুন...",
        freeAccount: "বিনামূল্যে অ্যাকাউন্ট তৈরি করুন",
        quotaPricingText: "Goshinsho সবার জন্য বিনামূল্যে। প্রতিটি প্রশ্নে কৃত্রিম বুদ্ধিমত্তা এবং ক্লাউড সার্ভার ব্যবহার করা হয়, যার প্রকৃত পরিচালন খরচ রয়েছে — যদি অ্যাপটি আপনার উপকারে আসে, তাহলে স্বেচ্ছামূলক অনুদান দিয়ে সহায়তা করার কথা বিবেচনা করুন।",
        makeDonation: "অনুদান দিন",
        subscriptionIntroEyebrow: "Goshinsho সম্পর্কে",
        subscriptionIntroTitle: "Goshinsho সবার জন্য বিনামূল্যে",
        subscriptionIntroText: "Goshinsho-তে প্রতিটি প্রশ্নে কৃত্রিম বুদ্ধিমত্তা এবং ক্লাউড সার্ভার ব্যবহার করা হয়, যার প্রকৃত পরিচালন খরচ রয়েছে। স্বেচ্ছামূলক অনুদান অ্যাপটি সচল রাখতে এবং উত্তর উন্নত করতে সাহায্য করে।",
        subscriptionIntroConfirm: "বুঝেছি",
        languageTitle: "অ্যাপের ভাষা নির্বাচন করুন",
        languageNote: "সাইটটি নির্বাচিত ভাষায় সমন্বিত হবে এবং আপনার পছন্দ এই ডিভাইসে সংরক্ষিত থাকবে।",
        back: "পিছনে",
        continue: "চালিয়ে যান",
        loading: "শিক্ষা পর্যালোচনা করা হচ্ছে...",
        checkingJapanese: "অনূদিত পাঠ্যে উপযুক্ত উত্তর পাওয়া যায়নি। মূল জাপানি পাঠ্য পরীক্ষা করা হচ্ছে — এতে ২ মিনিট পর্যন্ত সময় লাগতে পারে।",
        sourcesTitle: "চিহ্নিত উৎস",
        noSources: "বিস্তারিত উত্তরে মিলযুক্ত অংশ পাওয়া গেলে উৎস উত্তরের মূল অংশে প্রদর্শিত হয়।",
        like: "পছন্দ",
        dislike: "অপছন্দ",
        favorite: "পছন্দসইয়ে সংরক্ষণ করুন",
        showSources: "উৎস দেখুন",
        citationModeDirect: "সরাসরি",
        citationModeCited: "উদ্ধৃতি সহ",
        citationModeAria: "উত্তরের বিন্যাস",
        citeSources: "উদ্ধৃতি সহ আবার করুন",
        citingSources: "উদ্ধৃতি সহ আবার করা হচ্ছে...",
        share: "শেয়ার করুন",
        shareCopyLink: "লিংক কপি করুন",
        shareWhatsapp: "WhatsApp",
        shareEmail: "ইমেইল",
        shareCopied: "কপি হয়েছে",
        shareError: "ত্রুটি",
    },
    "Русский": {
        quotaRequiredTitle: "Требуется регистрация",
        quotaRequiredMessage:
            "Создайте бесплатный аккаунт, чтобы задавать вопросы -- доступ бесплатный премиум, с неограниченными вопросами, без необходимости платной подписки.",
        menu: "Меню",
        history: "История",
        newChat: "+ Новый чат",
        conversations: "Беседы",
        historySearch: "Поиск в истории...",
        noHistory: "Пока нет сохранённых бесед.",
        loginHistory: "Войдите, чтобы увидеть историю.",
        favorites: "Избранное",
        historyAria: "Открыть историю",
        subscribe: "Поддержать ❤",
        logout: "Выйти",
        login: "Вход",
        register: "Регистрация",
        contact: "Контакты",
        loginTitle: "Войти в аккаунт",
        password: "Пароль",
        rememberMe: "Оставаться в системе",
        signIn: "Войти",
        forgotPassword: "Забыли пароль",
        registerTitle: "Создать аккаунт",
        registerPolicyNote: "Бесплатная регистрация: премиум-доступ навсегда, с неограниченными вопросами. Без необходимости платной подписки.",
        confirmPassword: "Подтвердите пароль",
        createAccount: "Зарегистрироваться",
        humanCheck: "Я не робот",
        resetTitle: "Сброс пароля",
        resetNote: "Введите зарегистрированный email, чтобы получить ссылку для сброса пароля.",
        recoveryButton: "Отправить ссылку для восстановления",
        backToChat: "Вернуться к чату",
        newPasswordTitle: "Новый пароль",
        newPasswordNote: "Введите и подтвердите новый пароль.",
        newPasswordPlaceholder: "Новый пароль",
        confirmNewPassword: "Подтвердите новый пароль",
        updatePassword: "Обновить пароль",
        contactTitle: "Поддержка",
        name: "Имя",
        messageLabel: "Сообщение",
        send: "Отправить",
        loginHint: "Чтобы задавать вопросы, создайте аккаунт или войдите.",
        quotaSignupHint: "Создайте бесплатный аккаунт, чтобы задавать вопросы.",
        heroTitle: "Чем я могу помочь?",
        heroSubtitle: "Задайте вопрос об учении Мэйсю-Сама.",
        chatPlaceholder: "Введите ваш вопрос...",
        freeAccount: "Создать бесплатный аккаунт",
        quotaPricingText: "Goshinsho бесплатен для всех. Каждый вопрос использует искусственный интеллект и облачные серверы, которые имеют реальную стоимость эксплуатации — если приложение вам помогает, рассмотрите возможность поддержать его добровольным пожертвованием.",
        makeDonation: "Сделать пожертвование",
        subscriptionIntroEyebrow: "О Goshinsho",
        subscriptionIntroTitle: "Goshinsho бесплатен для всех",
        subscriptionIntroText: "Каждый вопрос в Goshinsho использует искусственный интеллект и облачные серверы, которые имеют реальную стоимость эксплуатации. Добровольные пожертвования помогают поддерживать доступность приложения и улучшать ответы.",
        subscriptionIntroConfirm: "Понятно",
        languageTitle: "Выберите язык приложения",
        languageNote: "Сайт переключится на выбранный язык, и настройка сохранится на этом устройстве.",
        back: "Назад",
        continue: "Продолжить",
        loading: "Изучаю тексты...",
        checkingJapanese: "Не удалось найти подходящий ответ в переведённых текстах. Проверяю оригинал на японском — это может занять до 2 минут.",
        sourcesTitle: "Найденные источники",
        noSources: "Источники появляются в тексте ответа, когда углублённый ответ находит совпадающие отрывки.",
        like: "Нравится",
        dislike: "Не нравится",
        favorite: "Сохранить в избранное",
        showSources: "Показать источники",
        citationModeDirect: "Прямой",
        citationModeCited: "С цитатами",
        citationModeAria: "Формат ответа",
        citeSources: "Повторить с цитатами",
        citingSources: "Повторяем с цитатами...",
        share: "Поделиться",
        shareCopyLink: "Скопировать ссылку",
        shareWhatsapp: "WhatsApp",
        shareEmail: "Email",
        shareCopied: "Скопировано",
        shareError: "Ошибка",
    },
    "اردو": {
        quotaRequiredTitle: "رجسٹریشن درکار ہے",
        quotaRequiredMessage:
            "سوالات پوچھنے کے لیے اپنا مفت اکاؤنٹ بنائیں -- یہ مفت پریمیم رسائی ہے، لامحدود سوالات، کسی ادا شدہ سبسکرپشن کی ضرورت نہیں۔",
        menu: "مینو",
        history: "تاریخچہ",
        newChat: "+ نئی گفتگو",
        conversations: "گفتگوئیں",
        historySearch: "تاریخچے میں تلاش کریں...",
        noHistory: "ابھی تک کوئی محفوظ شدہ گفتگو نہیں ہے۔",
        loginHistory: "اپنی تاریخچہ دیکھنے کے لیے لاگ ان کریں۔",
        favorites: "پسندیدہ",
        historyAria: "تاریخچہ کھولیں",
        subscribe: "معاونت کریں ❤",
        logout: "لاگ آؤٹ",
        login: "لاگ ان",
        register: "رجسٹر کریں",
        contact: "رابطہ کریں",
        loginTitle: "اپنے اکاؤنٹ تک رسائی حاصل کریں",
        password: "پاس ورڈ",
        rememberMe: "مجھے لاگ ان رکھیں",
        signIn: "سائن ان",
        forgotPassword: "پاس ورڈ بھول گئے",
        registerTitle: "اکاؤنٹ بنائیں",
        registerPolicyNote: "مفت رجسٹریشن: ہمیشہ کے لیے پریمیم رسائی، لامحدود سوالات۔ کسی ادا شدہ سبسکرپشن کی ضرورت نہیں۔",
        confirmPassword: "پاس ورڈ کی تصدیق کریں",
        createAccount: "اکاؤنٹ بنائیں",
        humanCheck: "میں انسان ہوں",
        resetTitle: "پاس ورڈ ری سیٹ کریں",
        resetNote: "پاس ورڈ ری سیٹ لنک حاصل کرنے کے لیے اپنا رجسٹرڈ ای میل درج کریں۔",
        recoveryButton: "ریکوری لنک بھیجیں",
        backToChat: "چیٹ پر واپس جائیں",
        newPasswordTitle: "نیا پاس ورڈ",
        newPasswordNote: "اپنا نیا پاس ورڈ درج کریں اور تصدیق کریں۔",
        newPasswordPlaceholder: "نیا پاس ورڈ",
        confirmNewPassword: "نئے پاس ورڈ کی تصدیق کریں",
        updatePassword: "پاس ورڈ اپ ڈیٹ کریں",
        contactTitle: "معاونت",
        name: "نام",
        messageLabel: "پیغام",
        send: "بھیجیں",
        loginHint: "سوالات پوچھنے کے لیے اکاؤنٹ بنائیں یا لاگ ان کریں۔",
        quotaSignupHint: "سوالات پوچھنے کے لیے اپنا مفت اکاؤنٹ بنائیں۔",
        heroTitle: "میں آپ کی کس طرح مدد کر سکتا ہوں؟",
        heroSubtitle: "میشو-ساما کی تعلیمات کے بارے میں سوال پوچھیں۔",
        chatPlaceholder: "اپنا سوال لکھیں...",
        freeAccount: "مفت اکاؤنٹ بنائیں",
        quotaPricingText: "Goshinsho سب کے لیے مفت ہے۔ ہر سوال کے لیے مصنوعی ذہانت اور کلاؤڈ سرورز استعمال ہوتے ہیں، جن کی حقیقی آپریٹنگ لاگت ہوتی ہے — اگر یہ ایپ آپ کے لیے مفید ہے تو رضاکارانہ عطیہ دے کر معاونت کرنے پر غور کریں۔",
        makeDonation: "عطیہ دیں",
        subscriptionIntroEyebrow: "Goshinsho کے بارے میں",
        subscriptionIntroTitle: "Goshinsho سب کے لیے مفت ہے",
        subscriptionIntroText: "Goshinsho پر ہر سوال کے لیے مصنوعی ذہانت اور کلاؤڈ سرورز استعمال ہوتے ہیں، جن کی حقیقی آپریٹنگ لاگت ہوتی ہے۔ رضاکارانہ عطیات ایپ کو دستیاب رکھنے اور جوابات بہتر بنانے میں مدد کرتے ہیں۔",
        subscriptionIntroConfirm: "سمجھ گیا",
        languageTitle: "ایپ کی زبان منتخب کریں",
        languageNote: "سائٹ منتخب کردہ زبان کے مطابق ایڈجسٹ ہو جائے گی اور آپ کی ترجیح اس ڈیوائس پر محفوظ ہو جائے گی۔",
        back: "واپس",
        continue: "جاری رکھیں",
        loading: "تعلیمات کا جائزہ لیا جا رہا ہے...",
        checkingJapanese: "ترجمہ شدہ متن میں مناسب جواب نہیں ملا۔ اصل جاپانی متن کی جانچ کی جا رہی ہے — اس میں 2 منٹ تک لگ سکتے ہیں۔",
        sourcesTitle: "شناخت شدہ ذرائع",
        noSources: "جب تفصیلی جواب میں مماثل اقتباسات ملتے ہیں تو ذرائع جواب کے متن میں ظاہر ہوتے ہیں۔",
        like: "پسند",
        dislike: "ناپسند",
        favorite: "پسندیدہ میں محفوظ کریں",
        showSources: "ذرائع دیکھیں",
        citationModeDirect: "براہ راست",
        citationModeCited: "حوالوں کے ساتھ",
        citationModeAria: "جواب کی شکل",
        citeSources: "حوالوں کے ساتھ دوبارہ کریں",
        citingSources: "حوالوں کے ساتھ دوبارہ کیا جا رہا ہے...",
        share: "شیئر کریں",
        shareCopyLink: "لنک کاپی کریں",
        shareWhatsapp: "WhatsApp",
        shareEmail: "ای میل",
        shareCopied: "کاپی ہو گیا",
        shareError: "خرابی",
    },
    "Indonesia": {
        quotaRequiredTitle: "Pendaftaran diperlukan",
        quotaRequiredMessage:
            "Buat akun gratis Anda untuk mengajukan pertanyaan -- akses premium gratis, dengan pertanyaan tanpa batas, tanpa perlu berlangganan berbayar.",
        menu: "Menu",
        history: "Riwayat",
        newChat: "+ Obrolan baru",
        conversations: "Percakapan",
        historySearch: "Cari riwayat...",
        noHistory: "Belum ada percakapan yang disimpan.",
        loginHistory: "Masuk untuk melihat riwayat Anda.",
        favorites: "Favorit",
        historyAria: "Buka riwayat",
        subscribe: "Dukung ❤",
        logout: "Keluar",
        login: "Masuk",
        register: "Daftar",
        contact: "Kontak",
        loginTitle: "Akses akun Anda",
        password: "Kata sandi",
        rememberMe: "Tetap masuk",
        signIn: "Masuk",
        forgotPassword: "Lupa kata sandi",
        registerTitle: "Buat akun",
        registerPolicyNote: "Pendaftaran gratis: akses premium selamanya, dengan pertanyaan tanpa batas. Tanpa perlu berlangganan berbayar.",
        confirmPassword: "Konfirmasi kata sandi",
        createAccount: "Buat akun",
        humanCheck: "Saya bukan robot",
        resetTitle: "Atur ulang kata sandi",
        resetNote: "Masukkan email terdaftar Anda untuk menerima tautan atur ulang kata sandi.",
        recoveryButton: "Kirim tautan pemulihan",
        backToChat: "Kembali ke obrolan",
        newPasswordTitle: "Kata sandi baru",
        newPasswordNote: "Masukkan dan konfirmasi kata sandi baru Anda.",
        newPasswordPlaceholder: "Kata sandi baru",
        confirmNewPassword: "Konfirmasi kata sandi baru",
        updatePassword: "Perbarui kata sandi",
        contactTitle: "Dukungan",
        name: "Nama",
        messageLabel: "Pesan",
        send: "Kirim",
        loginHint: "Untuk mengajukan pertanyaan, buat akun atau masuk.",
        quotaSignupHint: "Buat akun gratis Anda untuk mengajukan pertanyaan.",
        heroTitle: "Ada yang bisa saya bantu?",
        heroSubtitle: "Ajukan pertanyaan tentang tulisan Meishu-Sama.",
        chatPlaceholder: "Ketik pertanyaan Anda...",
        freeAccount: "Buat akun gratis",
        quotaPricingText: "Goshinsho gratis untuk semua orang. Setiap pertanyaan menggunakan kecerdasan buatan dan server cloud, yang memiliki biaya operasional nyata — jika aplikasi ini membantu Anda, pertimbangkan untuk mendukungnya dengan donasi sukarela.",
        makeDonation: "Buat donasi",
        subscriptionIntroEyebrow: "Tentang Goshinsho",
        subscriptionIntroTitle: "Goshinsho gratis untuk semua orang",
        subscriptionIntroText: "Setiap pertanyaan di Goshinsho menggunakan kecerdasan buatan dan server cloud, yang memiliki biaya operasional nyata. Donasi sukarela membantu menjaga aplikasi tetap tersedia dan meningkatkan kualitas jawaban.",
        subscriptionIntroConfirm: "Mengerti",
        languageTitle: "Pilih bahasa aplikasi",
        languageNote: "Situs akan disesuaikan dengan bahasa yang dipilih dan preferensi Anda akan disimpan di perangkat ini.",
        back: "Kembali",
        continue: "Lanjutkan",
        loading: "Memeriksa tulisan-tulisan...",
        checkingJapanese: "Saya tidak menemukan jawaban yang memadai dalam teks terjemahan. Sedang memeriksa naskah asli bahasa Jepang — ini bisa memakan waktu hingga 2 menit.",
        sourcesTitle: "Sumber yang teridentifikasi",
        noSources: "Sumber muncul di badan jawaban ketika jawaban mendalam menemukan kutipan yang sesuai.",
        like: "Suka",
        dislike: "Tidak suka",
        favorite: "Simpan sebagai favorit",
        showSources: "Lihat sumber",
        citationModeDirect: "Langsung",
        citationModeCited: "Dengan kutipan",
        citationModeAria: "Format jawaban",
        citeSources: "Ulangi dengan kutipan",
        citingSources: "Mengulangi dengan kutipan...",
        share: "Bagikan",
        shareCopyLink: "Salin tautan",
        shareWhatsapp: "WhatsApp",
        shareEmail: "Email",
        shareCopied: "Disalin",
        shareError: "Terjadi kesalahan",
    },
    "Deutsch": {
        quotaRequiredTitle: "Registrierung erforderlich",
        quotaRequiredMessage:
            "Erstellen Sie Ihr kostenloses Konto, um Fragen zu stellen -- der Zugang ist kostenlos Premium, mit unbegrenzten Fragen, kein kostenpflichtiges Abonnement nötig.",
        menu: "Menü",
        history: "Verlauf",
        newChat: "+ Neue Unterhaltung",
        conversations: "Unterhaltungen",
        historySearch: "Verlauf durchsuchen...",
        noHistory: "Noch keine gespeicherten Unterhaltungen.",
        loginHistory: "Melden Sie sich an, um Ihren Verlauf zu sehen.",
        favorites: "Favoriten",
        historyAria: "Verlauf öffnen",
        subscribe: "Unterstützen ❤",
        logout: "Abmelden",
        login: "Anmelden",
        register: "Registrieren",
        contact: "Kontakt",
        loginTitle: "Auf Ihr Konto zugreifen",
        password: "Passwort",
        rememberMe: "Angemeldet bleiben",
        signIn: "Anmelden",
        forgotPassword: "Passwort vergessen",
        registerTitle: "Konto erstellen",
        registerPolicyNote: "Kostenlose Registrierung: für immer Premium-Zugang, mit unbegrenzten Fragen. Kein kostenpflichtiges Abonnement nötig.",
        confirmPassword: "Passwort bestätigen",
        createAccount: "Konto erstellen",
        humanCheck: "Ich bin ein Mensch",
        resetTitle: "Passwort zurücksetzen",
        resetNote: "Geben Sie Ihre registrierte E-Mail-Adresse ein, um einen Link zum Zurücksetzen des Passworts zu erhalten.",
        recoveryButton: "Wiederherstellungslink senden",
        backToChat: "Zurück zum Chat",
        newPasswordTitle: "Neues Passwort",
        newPasswordNote: "Geben Sie Ihr neues Passwort ein und bestätigen Sie es.",
        newPasswordPlaceholder: "Neues Passwort",
        confirmNewPassword: "Neues Passwort bestätigen",
        updatePassword: "Passwort aktualisieren",
        contactTitle: "Support",
        name: "Name",
        messageLabel: "Nachricht",
        send: "Senden",
        loginHint: "Erstellen Sie ein Konto oder melden Sie sich an, um Fragen zu stellen.",
        quotaSignupHint: "Erstellen Sie Ihr kostenloses Konto, um Fragen zu stellen.",
        heroTitle: "Wie kann ich helfen?",
        heroSubtitle: "Stellen Sie eine Frage zu den Schriften von Meishu-Sama.",
        chatPlaceholder: "Geben Sie Ihre Frage ein...",
        freeAccount: "Kostenloses Konto erstellen",
        quotaPricingText: "Goshinsho ist für alle kostenlos. Jede Frage nutzt künstliche Intelligenz und Cloud-Server, die reale Betriebskosten verursachen — wenn die App dir hilft, erwäge, sie mit einer freiwilligen Spende zu unterstützen.",
        makeDonation: "Spenden",
        subscriptionIntroEyebrow: "Über Goshinsho",
        subscriptionIntroTitle: "Goshinsho ist für alle kostenlos",
        subscriptionIntroText: "Jede Frage bei Goshinsho nutzt künstliche Intelligenz und Cloud-Server, die reale Betriebskosten verursachen. Freiwillige Spenden helfen, die App verfügbar zu halten und die Antworten zu verbessern.",
        subscriptionIntroConfirm: "Verstanden",
        languageTitle: "App-Sprache wählen",
        languageNote: "Die Website wird an die gewählte Sprache angepasst, und Ihre Einstellung wird auf diesem Gerät gespeichert.",
        back: "Zurück",
        continue: "Weiter",
        loading: "Schriften werden durchsucht...",
        checkingJapanese: "In den übersetzten Texten wurde keine passende Antwort gefunden. Das japanische Original wird geprüft — dies kann bis zu 2 Minuten dauern.",
        sourcesTitle: "Identifizierte Quellen",
        noSources: "Quellen erscheinen im Antworttext, wenn die vertiefte Antwort passende Auszüge findet.",
        like: "Gefällt mir",
        dislike: "Gefällt mir nicht",
        favorite: "Als Favorit speichern",
        showSources: "Quellen anzeigen",
        citationModeDirect: "Direkt",
        citationModeCited: "Mit Zitaten",
        citationModeAria: "Antwortformat",
        citeSources: "Mit Zitaten wiederholen",
        citingSources: "Wird mit Zitaten wiederholt...",
        share: "Teilen",
        shareCopyLink: "Link kopieren",
        shareWhatsapp: "WhatsApp",
        shareEmail: "E-Mail",
        shareCopied: "Kopiert",
        shareError: "Fehler",
    },
};

let conversationHistory = [];
let selectedSupportTicketId = null;
let selectedLanguage = localStorage.getItem(languageStorageKey) || "Português";

// 2026-07-29: a URL do navegador nunca acompanhava a conversa ativa -- nem
// ao criar uma conversa nova, nem ao clicar "Nova Conversa". Isso fazia um
// simples F5/recarregar a página voltar para o que quer que estivesse na
// URL antes (ex.: uma conversa antiga aberta pela barra lateral), dando a
// impressão de que a conversa nova "sumiu" ou se fundiu com outras do
// mesmo dia -- os dados no banco sempre estiveram corretos e isolados por
// conversa, só a navegação do navegador ficava dessincronizada.
function syncConversationUrl(conversationId) {
    const url = new URL(window.location.href);
    if (conversationId) {
        url.searchParams.set("conversation_id", conversationId);
    } else {
        url.searchParams.delete("conversation_id");
    }
    window.history.replaceState({}, document.title, url.pathname + url.search);
}

function uiText(key) {
    const dictionary = uiTranslations[selectedLanguage] || uiTranslations.English || uiTranslations["Português"];
    return dictionary[key] || uiTranslations["Português"][key] || key;
}

function toggleSidebar(open) {
    if (sidebar) sidebar.classList.toggle("open", open);
    if (overlay) overlay.classList.toggle("open", open);
}

function openPanel(panelId) {
    let openedPanel = null;
    document.querySelectorAll(".floating-panel").forEach((panel) => {
        const shouldOpen = panel.id === panelId && !panel.classList.contains("open");
        panel.classList.toggle("open", shouldOpen);
        if (shouldOpen) openedPanel = panel;
    });
    if (openedPanel) {
        setTimeout(() => openedPanel.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    }
    if (panelId === "contact-panel") loadSupportTickets().catch(() => {});
}

function closePanels() {
    document.querySelectorAll(".floating-panel").forEach((panel) => panel.classList.remove("open"));
}

async function readNdjsonStream(response, onEvent) {
    if (!response.body) {
        throw new Error("Resposta inesperada do servidor.");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
            if (!line.trim()) continue;
            const event = JSON.parse(line);
            if (onEvent) onEvent(event);
            if (event.event === "done") finalData = event;
            if (event.event === "error") throw new Error(event.error || "Erro ao enviar mensagem.");
        }
    }

    if (buffer.trim()) {
        const event = JSON.parse(buffer);
        if (onEvent) onEvent(event);
        if (event.event === "done") finalData = event;
        if (event.event === "error") throw new Error(event.error || "Erro ao enviar mensagem.");
    }

    if (!finalData) {
        throw new Error("Resposta incompleta do servidor.");
    }
    return finalData;
}

async function readJson(response) {
    const text = await response.text();
    try {
        return JSON.parse(text);
    } catch {
        return {
            error: response.redirected
                ? "Sua sessão expirou. Faça login novamente."
                : "Resposta inesperada do servidor.",
            raw: text,
        };
    }
}

function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatInlineMarkdown(text) {
    return escapeHtml(text)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function renderAssistantMarkdown(text) {
    const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let listOpen = false;

    function closeList() {
        if (listOpen) {
            html.push("</ul>");
            listOpen = false;
        }
    }

    lines.forEach((line) => {
        const trimmed = line.trim();
        if (!trimmed) {
            closeList();
            return;
        }

        const heading = trimmed.match(/^#{1,4}\s+(.+)$/);
        if (heading) {
            closeList();
            html.push(`<h3>${formatInlineMarkdown(heading[1])}</h3>`);
            return;
        }

        const quote = trimmed.match(/^>\s?(.+)$/);
        if (quote) {
            closeList();
            html.push(`<blockquote>${formatInlineMarkdown(quote[1])}</blockquote>`);
            return;
        }

        const bullet = trimmed.match(/^[-*]\s+(.+)$/);
        if (bullet) {
            if (!listOpen) {
                html.push("<ul>");
                listOpen = true;
            }
            html.push(`<li>${formatInlineMarkdown(bullet[1])}</li>`);
            return;
        }

        closeList();
        html.push(`<p>${formatInlineMarkdown(trimmed)}</p>`);
    });

    closeList();
    return html.join("");
}

function setBubbleContent(bubble, content, role = "assistant") {
    if (!bubble) return;
    if (role === "assistant") {
        bubble.dataset.rawContent = content || "";
        bubble.innerHTML = renderAssistantMarkdown(content || "");
        return;
    }
    bubble.textContent = content || "";
}

function getRetrievalMode() {
    const language = languageInput?.value || selectedLanguage;
    if (language && language !== "Português") return "jp_agentic";
    return document.body.dataset.retrievalMode || "jp_agentic";
}

function getCitationMode() {
    return document.querySelector('input[name="citation-mode"]:checked')?.value || "direta";
}

function handleChatStatusEvent(loading, event) {
    if (event.event !== "status" || !event.code) return;
    if (event.code === "checking_japanese") {
        setBubbleContent(loading, uiText("checkingJapanese"), "assistant");
    }
}

function enterChatMode() {
    document.querySelector(".app-shell")?.classList.remove("initial-view");
    document.querySelector(".hero")?.classList.add("compact");
}

function temporaryButtonText(button, text) {
    if (!button) return;
    const previous = button.innerHTML;
    button.innerHTML = text;
    setTimeout(() => {
        button.innerHTML = previous;
    }, 1800);
}

function messageActionsHtml() {
    return `
        <button type="button" data-feedback="like" aria-label="${escapeHtml(uiText("like"))}" title="${escapeHtml(uiText("like"))}">👍</button>
        <button type="button" data-feedback="dislike" aria-label="${escapeHtml(uiText("dislike"))}" title="${escapeHtml(uiText("dislike"))}">👎</button>
        <button type="button" data-favorite-response aria-label="${escapeHtml(uiText("favorite"))}" title="${escapeHtml(uiText("favorite"))}">☆</button>
        <button type="button" data-show-sources aria-label="${escapeHtml(uiText("showSources"))}" title="${escapeHtml(uiText("showSources"))}">📚</button>
        <button type="button" data-cite-sources aria-label="${escapeHtml(uiText("citeSources"))}" title="${escapeHtml(uiText("citeSources"))}">📖</button>
        <button type="button" data-share-response aria-label="${escapeHtml(uiText("share"))}" title="${escapeHtml(uiText("share"))}">
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <path d="M8.7 10.7 15.3 6.3M8.7 13.3l6.6 4.4"></path>
            </svg>
        </button>
    `;
}

function appendMessage(role, content, messageId = null, { pending = false } = {}) {
    if (!chat) return null;
    const article = document.createElement("article");
    article.className = `message ${role}`;
    if (messageId) article.dataset.messageId = messageId;
    if (pending) article.classList.add("is-pending");

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    setBubbleContent(bubble, content, role);
    article.appendChild(bubble);

    if (role === "assistant") {
        const actions = document.createElement("div");
        actions.className = "message-actions";
        actions.setAttribute("aria-label", "Ações da resposta");
        actions.innerHTML = messageActionsHtml();
        article.appendChild(actions);
    }

    chat.appendChild(article);
    article.scrollIntoView({ behavior: "smooth", block: "start" });
    return bubble;
}

function updateQuotaCard(status) {
    if (!status) return;
    if (quotaCard) quotaCard.dataset.quota = JSON.stringify(status);

    const needsSignup = status.requires_login || status.plan === "cadastro_necessario";
    if (needsSignup) {
        // Título/mensagem do backend são só em português (plano fixo, sem variação por usuário);
        // aqui usamos a versão traduzida no idioma escolhido em vez do texto vindo da API.
        if (quotaTitle) quotaTitle.textContent = uiText("quotaRequiredTitle");
        if (quotaMessage) quotaMessage.textContent = uiText("quotaRequiredMessage");
    } else {
        if (quotaTitle) quotaTitle.textContent = status.label || "Plano";
        if (quotaMessage) quotaMessage.textContent = status.message || "";
    }
    if (quotaPricingNote && status.pricing_explanation) {
        quotaPricingNote.textContent = status.pricing_explanation;
        quotaPricingNote.hidden = false;
    }

    if (quotaSignupHint) {
        quotaSignupHint.classList.toggle("visible", needsSignup);
        if (needsSignup) {
            quotaSignupHint.textContent = uiText("quotaSignupHint");
        }
    }
    if (quotaSignupButton) {
        quotaSignupButton.classList.toggle("quota-highlight", needsSignup);
    }

    if (status.show_subscription_intro) {
        maybeShowSubscriptionIntro(status);
    }
}

function openSubscriptionIntroDialog() {
    if (!subscriptionIntroDialog) return;
    subscriptionIntroDialog.classList.add("open");
    subscriptionIntroDialog.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
}

function closeSubscriptionIntroDialog() {
    if (!subscriptionIntroDialog) return;
    subscriptionIntroDialog.classList.remove("open");
    subscriptionIntroDialog.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    localStorage.setItem(subscriptionIntroStorageKey, "1");
}

function maybeShowSubscriptionIntro(status) {
    if (!isLoggedIn || status?.is_premium || !status?.show_subscription_intro) return;
    if (localStorage.getItem(subscriptionIntroStorageKey) === "1") return;
    openSubscriptionIntroDialog();
}

function validatePremiumGrantForm(formData) {
    const requiredFields = [
        ["full_name", "Informe seu nome completo."],
        ["phone", "Informe um telefone ou WhatsApp."],
        ["country", "Informe seu país."],
        ["city_state", "Informe sua cidade e estado ou região."],
        ["financial_situation", "Selecione sua situação financeira."],
    ];
    for (const [name, message] of requiredFields) {
        if (!(formData.get(name) || "").trim()) return message;
    }
    const reason = (formData.get("reason") || "").trim();
    if (reason.length < 20) {
        return "No campo «Por que você precisa de acesso gratuito?», descreva sua situação com um pouco mais de detalhe (pelo menos 20 caracteres).";
    }
    const usageIntent = (formData.get("usage_intent") || "").trim();
    if (usageIntent.length < 10) {
        return "No campo «Como pretende usar o Goshinsho?», escreva uma frase curta — por exemplo: «Estudo pessoal dos escritos de Meishu-Sama».";
    }
    if (formData.get("truthfulness_ack") !== "1") {
        return "Confirme que as informações prestadas são verdadeiras.";
    }
    if (formData.get("data_consent") !== "1") {
        return "Autorize o uso dos dados para análise desta solicitação.";
    }
    return null;
}

function showSignupRequiredMessage(bubble, message) {
    if (!bubble) return;
    bubble.innerHTML = `
        <p class="quota-limit-text">${escapeHtml(message)}</p>
        <button type="button" class="inline-signup-btn" data-panel="register-panel">Criar conta gratuita</button>
    `;
    bubble.querySelector("[data-panel='register-panel']")?.addEventListener("click", () => openPanel("register-panel"));
}

function maybePromptSignup(data) {
    if (!data?.signup_recommended && !data?.requires_login && data?.quota_status?.plan !== "cadastro_necessario") return;
    openPanel("register-panel");
}

function loadFavorites() {
    try {
        return JSON.parse(localStorage.getItem(favoritesStorageKey) || "[]");
    } catch {
        return [];
    }
}

function saveFavorites(favorites) {
    localStorage.setItem(favoritesStorageKey, JSON.stringify(favorites.slice(0, 30)));
}

function renderFavorites() {
    if (!favoritesList) return;
    const favorites = loadFavorites();
    favoritesList.innerHTML = "";
    if (!favorites.length) {
        favoritesList.innerHTML = '<p class="muted">Nenhuma resposta favorita ainda.</p>';
        return;
    }
    favorites.forEach((favorite) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "favorite-item";
        button.innerHTML = `<strong>${escapeHtml(favorite.title || "Resposta favorita")}</strong><span>${escapeHtml((favorite.content || "").slice(0, 120))}</span>`;
        button.addEventListener("click", () => {
            appendMessage("assistant", favorite.content || "");
            toggleSidebar(false);
        });
        favoritesList.appendChild(button);
    });
}

function toggleFavorite(article, button) {
    const content = article?.querySelector(".bubble")?.textContent || "";
    if (!content) return;
    const messageId = article?.dataset.messageId || content.slice(0, 64);
    const favorites = loadFavorites();
    const existingIndex = favorites.findIndex((favorite) => favorite.id === messageId);
    if (existingIndex >= 0) {
        favorites.splice(existingIndex, 1);
        button?.classList.remove("active");
        if (button) button.textContent = "☆";
    } else {
        favorites.unshift({ id: messageId, title: content.slice(0, 48), content });
        button?.classList.add("active");
        if (button) button.textContent = "★";
    }
    saveFavorites(favorites);
    renderFavorites();
}

function readArticleSources(article) {
    // 2026-07-20: fontes reais, lidas do marcador do backend (ver
    // routes.py resolve_source_titles) -- antes vasculhava o texto da
    // resposta por palavra-chave ("fonte"/"livro"/"ensinamento"...), quase
    // sempre devolvendo pedaços da própria resposta (achado do usuário: o
    // modo direto nunca cita fonte no texto, então qualquer frase
    // teológica normal batia no filtro).
    const raw = article?.dataset.sources;
    if (!raw) return [];
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

function toggleSourcesPanel(article) {
    let panel = article.querySelector(".source-panel");
    if (panel) {
        panel.remove();
        return;
    }
    const sources = readArticleSources(article);
    panel = document.createElement("div");
    panel.className = "source-panel";
    const body = sources.length
        ? sources.map((source) => `<p>${escapeHtml(source)}</p>`).join("")
        : `<p>${escapeHtml(uiText("noSources"))}</p>`;
    panel.innerHTML = `<strong>${escapeHtml(uiText("sourcesTitle"))}</strong>${body}`;
    article.appendChild(panel);
}

function findQuestionForArticle(article) {
    if (!article) return "";
    let node = article.previousElementSibling;
    while (node) {
        if (node.classList?.contains("user")) {
            return node.querySelector(".bubble")?.textContent?.trim() || "";
        }
        node = node.previousElementSibling;
    }
    return "";
}

function closeShareMenu() {
    document.querySelector(".share-menu")?.remove();
    document.removeEventListener("click", closeShareMenuOnOutsideClick, true);
}

function closeShareMenuOnOutsideClick(event) {
    if (!event.target.closest(".share-menu") && !event.target.closest("[data-share-response]")) {
        closeShareMenu();
    }
}

const SHARE_ANSWER_PREVIEW_CHARS = 400;

function openShareMenu(button, { question, answer, url }) {
    closeShareMenu();
    const trimmedAnswer =
        answer.length > SHARE_ANSWER_PREVIEW_CHARS
            ? `${answer.slice(0, SHARE_ANSWER_PREVIEW_CHARS).trim()}…`
            : answer;
    const text = question ? `${question}\n\n${trimmedAnswer}\n\n${url}` : `${trimmedAnswer}\n\n${url}`;
    const menu = document.createElement("div");
    menu.className = "share-menu";
    menu.innerHTML = `
        <button type="button" data-action="copy">${escapeHtml(uiText("shareCopyLink"))}</button>
        <a data-action="whatsapp" href="https://wa.me/?text=${encodeURIComponent(text)}" target="_blank" rel="noopener">${escapeHtml(uiText("shareWhatsapp"))}</a>
        <a data-action="email" href="mailto:?subject=${encodeURIComponent("Goshinsho")}&body=${encodeURIComponent(text)}">${escapeHtml(uiText("shareEmail"))}</a>
    `;
    menu.querySelector('[data-action="copy"]').addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(text);
            temporaryButtonText(button, uiText("shareCopied"));
        } catch {
            temporaryButtonText(button, uiText("shareError"));
        }
        closeShareMenu();
    });
    menu.querySelectorAll("a[data-action]").forEach((link) => {
        link.addEventListener("click", () => closeShareMenu());
    });
    button.closest(".message-actions")?.appendChild(menu);
    setTimeout(() => document.addEventListener("click", closeShareMenuOnOutsideClick, true), 0);
}

async function shareResponse(article, button) {
    // 2026-08-03: achado real -- `.textContent` descarta a estrutura de
    // blocos (### tema virou <h3>, parágrafos viraram <p>) sem inserir
    // nenhuma quebra de linha entre eles, grudando o título no texto
    // seguinte ao compartilhar. `data-raw-content` (setado em
    // setBubbleContent) guarda o texto original com as quebras de linha
    // reais -- usar isso quando disponível (mensagens da sessão atual);
    // cai pra `.textContent` só pra histórico recarregado do servidor,
    // que nunca passa por renderAssistantMarkdown (mostra o markdown cru
    // como texto simples, sem estrutura pra perder).
    const bubble = article?.querySelector(".bubble");
    const answer = (bubble?.dataset.rawContent || bubble?.textContent || "").trim();
    const question = findQuestionForArticle(article);
    const messageId = article?.dataset.messageId;
    const url = messageId ? `${window.location.origin}/resposta/${messageId}` : window.location.href;

    if (navigator.share && messageId) {
        try {
            await navigator.share({
                title: "Goshinsho",
                text: question ? `${question}\n\n${answer}` : answer,
                url,
            });
            return;
        } catch {
            /* usuário cancelou o share nativo ou não suportado; cai para o menu visível */
        }
    }
    openShareMenu(button, { question, answer, url });
}

function buildLanguageDialog() {
    if (!languageInput || !languageOptions) return;
    languageOptions.innerHTML = "";
    Array.from(languageInput.options).forEach((option) => {
        const label = document.createElement("label");
        label.className = `language-option ${option.value === selectedLanguage ? "active" : ""}`;
        label.innerHTML = `<input type="radio" name="language-option" value="${escapeHtml(option.value)}" ${option.value === selectedLanguage ? "checked" : ""}> <span>${escapeHtml(option.value)}</span>`;
        label.addEventListener("click", () => {
            selectedLanguage = option.value;
            languageOptions.querySelectorAll(".language-option").forEach((item) => item.classList.remove("active"));
            label.classList.add("active");
        });
        languageOptions.appendChild(label);
    });
}

function translateInterface(language) {
    const dictionary = uiTranslations[language] || uiTranslations.English || uiTranslations["Português"];
    document.documentElement.lang = language === "Português" ? "pt-BR" : language;

    document.querySelectorAll("[data-i18n]").forEach((element) => {
        const key = element.dataset.i18n;
        if (dictionary[key]) element.textContent = dictionary[key];
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
        const key = element.dataset.i18nPlaceholder;
        if (dictionary[key]) element.setAttribute("placeholder", dictionary[key]);
    });

    document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
        const key = element.dataset.i18nAria;
        if (dictionary[key]) element.setAttribute("aria-label", dictionary[key]);
    });

    document.querySelectorAll("[data-feedback='like']").forEach((button) => {
        button.setAttribute("aria-label", uiText("like"));
        button.setAttribute("title", uiText("like"));
    });
    document.querySelectorAll("[data-feedback='dislike']").forEach((button) => {
        button.setAttribute("aria-label", uiText("dislike"));
        button.setAttribute("title", uiText("dislike"));
    });
    document.querySelectorAll("[data-favorite-response]").forEach((button) => {
        button.setAttribute("aria-label", uiText("favorite"));
        button.setAttribute("title", uiText("favorite"));
    });
    document.querySelectorAll("[data-show-sources]").forEach((button) => {
        button.setAttribute("aria-label", uiText("showSources"));
        button.setAttribute("title", uiText("showSources"));
    });
    document.querySelectorAll("[data-share-response]").forEach((button) => {
        button.setAttribute("aria-label", uiText("share"));
        button.setAttribute("title", uiText("share"));
    });
    if (quotaCard?.dataset.quota) {
        try {
            updateQuotaCard(JSON.parse(quotaCard.dataset.quota));
        } catch {
            /* ignore invalid quota payload */
        }
    }
}

function applyLanguage(language) {
    selectedLanguage = language || "Português";
    if (languageInput) languageInput.value = selectedLanguage;
    if (languageButton) languageButton.textContent = languageLabels[selectedLanguage] || `Idioma: ${selectedLanguage}`;
    localStorage.setItem(languageStorageKey, selectedLanguage);
    translateInterface(selectedLanguage);
}

function openLanguageDialog() {
    buildLanguageDialog();
    if (languageDialog) {
        languageDialog.classList.add("open");
        languageDialog.setAttribute("aria-hidden", "false");
        document.body.classList.add("modal-open");
    }
}

function closeLanguageDialog() {
    if (languageDialog) {
        languageDialog.classList.remove("open");
        languageDialog.setAttribute("aria-hidden", "true");
        document.body.classList.remove("modal-open");
    }
}

function openRequestedPanelFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const panel = params.get("panel");
    if (params.get("confirmed") === "1") {
        showTransientNotice("E-mail confirmado! Faça login para continuar.", "success");
    }
    // 2026-08-03: cadastro real concluído (routes.py só acrescenta este
    // parâmetro nos casos de sucesso genuíno, nunca em bot/erro) -- dispara
    // o evento de conversão do Meta Pixel (cookie_consent.js, sem efeito
    // se o usuário não tiver consentido) e limpa o parâmetro da URL pra não
    // disparar de novo num refresh.
    if (params.get("signup") === "1") {
        if (typeof window.goshinshoTrackConversion === "function") {
            window.goshinshoTrackConversion("CompleteRegistration");
        }
        params.delete("signup");
        const cleanQuery = params.toString();
        const cleanUrl = window.location.pathname + (cleanQuery ? `?${cleanQuery}` : "") + window.location.hash;
        window.history.replaceState({}, "", cleanUrl);
    }
    const panelMap = {
        login: "login-panel",
        register: "register-panel",
        cadastro: "register-panel",
        contact: "contact-panel",
        contato: "contact-panel",
        "premium-grant": "premium-grant-panel",
        grant: "premium-grant-panel",
    };
    if (panelMap[panel]) openPanel(panelMap[panel]);
}

function showTransientNotice(message, kind = "success") {
    const box = document.createElement("div");
    box.className = `flash ${kind}`;
    box.textContent = message;
    const host = document.querySelector(".flash-list") || document.querySelector(".app-shell");
    if (!host) return;
    if (host.classList.contains("app-shell")) {
        host.insertAdjacentElement("afterbegin", box);
    } else {
        host.appendChild(box);
    }
    window.setTimeout(() => box.remove(), 12000);
}

function initAuthHashHandler() {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const accessToken = hash.get("access_token");
    const type = hash.get("type");
    if (!accessToken) return;
    if (type === "recovery" || !type) {
        openPanel("reset-password-panel");
        return;
    }
    if (type === "signup" || type === "email" || type === "magiclink") {
        const cleanUrl = `${window.location.pathname}?panel=login&confirmed=1`;
        history.replaceState(null, "", cleanUrl);
        openPanel("login-panel");
        showTransientNotice("E-mail confirmado! Faça login para continuar.", "success");
    }
}

menuButton?.addEventListener("click", () => toggleSidebar(true));
overlay?.addEventListener("click", () => toggleSidebar(false));

document.querySelectorAll("[data-panel]").forEach((button) => {
    button.addEventListener("click", () => openPanel(button.dataset.panel));
});

document.querySelectorAll("[data-close-panels]").forEach((button) => {
    button.addEventListener("click", closePanels);
});

document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
        const input = button.closest(".password-field")?.querySelector("input");
        if (!input) return;
        input.type = input.type === "password" ? "text" : "password";
        button.setAttribute("aria-label", input.type === "password" ? "Mostrar senha" : "Ocultar senha");
    });
});

languageButton?.addEventListener("click", openLanguageDialog);
languageConfirm?.addEventListener("click", () => {
    const checked = languageOptions?.querySelector("input:checked");
    applyLanguage(checked?.value || selectedLanguage);
    closeLanguageDialog();
});
languageCancel?.addEventListener("click", closeLanguageDialog);

languageDialog?.addEventListener("click", (event) => {
    if (event.target === languageDialog) closeLanguageDialog();
});

historySearch?.addEventListener("input", () => {
    const term = historySearch.value.toLowerCase();
    document.querySelectorAll(".conversation-link").forEach((link) => {
        link.style.display = link.textContent.toLowerCase().includes(term) ? "" : "none";
    });
});

newChatButton?.addEventListener("click", async () => {
    await fetch("/api/conversations/new", { method: "POST" });
    if (chat) {
        chat.dataset.conversationId = "";
        chat.innerHTML = "";
    }
    conversationHistory = [];
    syncConversationUrl(null);
    toggleSidebar(false);
});

messageInput?.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${messageInput.scrollHeight}px`;
});

chatForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = messageInput?.value.trim();
    if (!message) return;

    if (!isLoggedIn) {
        openPanel("register-panel");
        return;
    }

    enterChatMode();
    appendMessage("user", message);
    conversationHistory.push({ role: "user", content: message });
    messageInput.value = "";
    messageInput.style.height = "auto";

    const loading = appendMessage("assistant", uiText("loading"), null, { pending: true });
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                language: languageInput?.value || selectedLanguage,
                retrieval_mode: getRetrievalMode(),
                citation_mode: getCitationMode(),
                conversation_id: chat?.dataset.conversationId,
                history: conversationHistory.slice(-8),
            }),
        });
        const contentType = response.headers.get("content-type") || "";
        const data = contentType.includes("application/x-ndjson")
            ? await readNdjsonStream(response, (event) => handleChatStatusEvent(loading, event))
            : await readJson(response);
        if (!response.ok && !contentType.includes("application/x-ndjson")) {
            updateQuotaCard(data.quota_status);
            if (data.email_confirmation_required) {
                loading?.closest(".message")?.classList.remove("is-pending");
                setBubbleContent(loading, data.error || "Confirme seu e-mail antes de fazer perguntas.", "assistant");
                return;
            }
            if (data.quota_limit_reached && data.quota_status?.show_subscription_intro) {
                maybeShowSubscriptionIntro(data.quota_status);
            }
            if (data.requires_login || data.quota_status?.plan === "cadastro_necessario") {
                loading?.closest(".message")?.classList.remove("is-pending");
                showSignupRequiredMessage(loading, data.error || "Para fazer perguntas, crie sua conta gratuita.");
                maybePromptSignup(data);
                return;
            }
            throw new Error(data.error || "Erro ao enviar mensagem.");
        }
        if (chat) chat.dataset.conversationId = data.conversation_id || "";
        if (data.conversation_id) syncConversationUrl(data.conversation_id);
        setBubbleContent(loading, data.answer || "", "assistant");
        const article = loading?.closest(".message");
        article?.classList.remove("is-pending");
        if (article && data.assistant_message_id) article.dataset.messageId = data.assistant_message_id;
        if (article) article.dataset.sources = JSON.stringify(data.sources || []);
        updateQuotaCard(data.quota_status);
        conversationHistory.push({ role: "assistant", content: data.answer || "" });
        article?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        loading?.closest(".message")?.classList.remove("is-pending");
        setBubbleContent(loading, error.message, "assistant");
    }
});

async function requestCiteSources(button) {
    if (!isLoggedIn) {
        openPanel("register-panel");
        return;
    }
    button.disabled = true;
    const loading = appendMessage("assistant", uiText("citingSources"), null, { pending: true });
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: "",
                language: languageInput?.value || selectedLanguage,
                retrieval_mode: getRetrievalMode(),
                conversation_id: chat?.dataset.conversationId,
                history: conversationHistory.slice(-8),
                cite_sources: true,
            }),
        });
        const contentType = response.headers.get("content-type") || "";
        const data = contentType.includes("application/x-ndjson")
            ? await readNdjsonStream(response, (event) => handleChatStatusEvent(loading, event))
            : await readJson(response);
        if (!response.ok && !contentType.includes("application/x-ndjson")) {
            throw new Error(data.error || "Erro ao buscar as citações.");
        }
        if (chat) chat.dataset.conversationId = data.conversation_id || "";
        setBubbleContent(loading, data.answer || "", "assistant");
        const article = loading?.closest(".message");
        article?.classList.remove("is-pending");
        if (article && data.assistant_message_id) article.dataset.messageId = data.assistant_message_id;
        updateQuotaCard(data.quota_status);
        conversationHistory.push({ role: "assistant", content: data.answer || "" });
        article?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        loading?.closest(".message")?.classList.remove("is-pending");
        setBubbleContent(loading, error.message, "assistant");
    } finally {
        button.disabled = false;
    }
}

chat?.addEventListener("click", async (event) => {
    const feedbackButton = event.target.closest("[data-feedback]");
    const favoriteButton = event.target.closest("[data-favorite-response]");
    const sourcesButton = event.target.closest("[data-show-sources]");
    const citeSourcesButton = event.target.closest("[data-cite-sources]");
    const shareButton = event.target.closest("[data-share-response]");
    const article = event.target.closest(".message");

    if (favoriteButton) {
        toggleFavorite(article, favoriteButton);
        return;
    }
    if (sourcesButton) {
        toggleSourcesPanel(article);
        return;
    }
    if (citeSourcesButton) {
        await requestCiteSources(citeSourcesButton);
        return;
    }
    if (shareButton) {
        await shareResponse(article, shareButton);
        return;
    }
    if (!feedbackButton) return;

    const messageId = article?.dataset.messageId;
    if (!messageId) {
        alert("Faça login para registrar feedback em respostas salvas.");
        return;
    }
    const response = await fetch(`/api/messages/${messageId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: feedbackButton.dataset.feedback }),
    });
    const data = await readJson(response);
    if (response.ok) {
        feedbackButton.classList.add("active");
        temporaryButtonText(feedbackButton, "OK");
    } else {
        alert(data.error || "Erro ao registrar feedback.");
    }
});

resetPasswordPanel?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const params = new URLSearchParams(window.location.search);
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const accessToken = params.get("access_token") || hash.get("access_token");
    const formData = new FormData(resetPasswordPanel);
    resetPasswordMessage.textContent = "Atualizando senha...";
    const response = await fetch("/api/auth/update-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            access_token: accessToken,
            password: formData.get("password"),
            confirm_password: formData.get("confirm_password"),
        }),
    });
    const data = await readJson(response);
    resetPasswordMessage.textContent = response.ok ? data.message : data.error || "Erro ao atualizar senha.";
    if (response.ok) {
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

function renderSupportTickets(tickets) {
    if (!supportTicketList) return;
    supportTicketList.innerHTML = "";
    if (!tickets.length) {
        supportTicketList.innerHTML = '<p class="panel-note">Nenhum atendimento aberto ainda.</p>';
        return;
    }
    tickets.slice(0, 8).forEach((ticket) => {
        const card = document.createElement("button");
        card.type = "button";
        card.dataset.ticketId = ticket.id;
        card.className = `support-ticket-card ${ticket.id === selectedSupportTicketId ? "active" : ""}`;
        card.innerHTML = `<strong>${escapeHtml(ticket.subject || "Atendimento")}</strong><span>${escapeHtml(ticket.category_label || ticket.category || "Suporte")} · ${escapeHtml(ticket.status || "open")}</span><small>${ticket.messages?.length || 0} mensagem(ns)</small>`;
        card.addEventListener("click", () => renderSupportTicketDetail(ticket));
        supportTicketList.appendChild(card);
    });
}

function renderSupportTicketDetail(ticket) {
    if (!supportTicketDetail || !supportTicketThread) return;
    selectedSupportTicketId = ticket.id;
    supportTicketDetail.hidden = false;
    supportTicketThread.className = "support-thread";
    supportTicketThread.innerHTML = `<strong>${escapeHtml(ticket.subject || "Atendimento")}</strong>${(ticket.messages || []).map((message) => `<div class="support-thread-message ${message.role === "admin" ? "admin" : "user"}"><strong>${message.role === "admin" ? "Suporte" : "Você"}</strong><p>${escapeHtml(message.content || "")}</p></div>`).join("")}`;
    supportTicketList?.querySelectorAll(".support-ticket-card").forEach((card) => card.classList.remove("active"));
    supportTicketList?.querySelector(`[data-ticket-id="${ticket.id}"]`)?.classList.add("active");
}

async function loadSupportTickets() {
    if (!supportTicketList) return;
    const response = await fetch("/api/support/tickets");
    const data = await readJson(response);
    if (response.ok) {
        const tickets = data.tickets || [];
        renderSupportTickets(tickets);
        if (selectedSupportTicketId) {
            const selected = tickets.find((ticket) => ticket.id === selectedSupportTicketId);
            if (selected) renderSupportTicketDetail(selected);
        }
    }
}

supportPanel?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(supportPanel);
    if (supportMessage) supportMessage.textContent = "Abrindo atendimento...";
    const response = await fetch("/api/support/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name: formData.get("name"),
            email: formData.get("email"),
            category: formData.get("category"),
            subject: formData.get("subject"),
            message: formData.get("message"),
            language: languageInput?.value || selectedLanguage,
        }),
    });
    const data = await readJson(response);
    if (!response.ok) {
        if (supportMessage) supportMessage.textContent = data.error || "Erro ao abrir atendimento.";
        return;
    }
    supportPanel.reset();
    if (supportMessage) supportMessage.textContent = "Atendimento aberto com sucesso.";
    selectedSupportTicketId = data.ticket?.id || null;
    if (data.ticket) renderSupportTicketDetail(data.ticket);
    await loadSupportTickets();
});

supportReplyButton?.addEventListener("click", async () => {
    const message = (supportReplyInput?.value || "").trim();
    if (!selectedSupportTicketId || !message) return;
    const response = await fetch(`/api/support/tickets/${selectedSupportTicketId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
    });
    const data = await readJson(response);
    if (response.ok) {
        supportReplyInput.value = "";
        renderSupportTicketDetail(data.ticket);
        await loadSupportTickets();
    } else if (supportMessage) {
        supportMessage.textContent = data.error || "Erro ao responder.";
    }
});

premiumGrantPanel?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!isLoggedIn) {
        openPanel("register-panel");
        return;
    }
    const formData = new FormData(premiumGrantPanel);
    const validationError = validatePremiumGrantForm(formData);
    if (validationError) {
        if (premiumGrantMessage) premiumGrantMessage.textContent = validationError;
        return;
    }
    const payload = Object.fromEntries(formData.entries());
    payload.truthfulness_ack = formData.get("truthfulness_ack") === "1";
    payload.data_consent = formData.get("data_consent") === "1";
    if (premiumGrantMessage) premiumGrantMessage.textContent = "Enviando solicitação...";
    try {
        const response = await fetch("/api/premium-grant", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await readJson(response);
        if (!response.ok) {
            if (premiumGrantMessage) premiumGrantMessage.textContent = data.error || "Erro ao enviar solicitação.";
            return;
        }
        if (premiumGrantMessage) {
            premiumGrantMessage.textContent = data.message || "Solicitação enviada com sucesso.";
        }
        premiumGrantPanel.reset();
        setTimeout(() => window.location.reload(), 1200);
    } catch (error) {
        if (premiumGrantMessage) premiumGrantMessage.textContent = error.message;
    }
});

function initSignupShield() {
    const field = document.getElementById("signup-started");
    if (field) field.value = String(Math.floor(Date.now() / 1000));
}

subscriptionIntroConfirm?.addEventListener("click", closeSubscriptionIntroDialog);
subscriptionIntroGrant?.addEventListener("click", () => {
    closeSubscriptionIntroDialog();
    window.location.href = "/doacao";
});
subscriptionIntroDialog?.addEventListener("click", (event) => {
    if (event.target === subscriptionIntroDialog) closeSubscriptionIntroDialog();
});

applyLanguage(selectedLanguage);
buildLanguageDialog();
renderFavorites();
initSignupShield();
initAuthHashHandler();
openRequestedPanelFromUrl();
if (quotaCard?.dataset.quota) {
    try {
        updateQuotaCard(JSON.parse(quotaCard.dataset.quota));
    } catch {
        /* ignore invalid quota payload */
    }
}
document.querySelectorAll(".message.assistant .bubble").forEach((bubble) => {
    setBubbleContent(bubble, bubble.dataset.rawContent || bubble.textContent, "assistant");
});

if (!localStorage.getItem(languageStorageKey)) {
    openLanguageDialog();
}
