#!/usr/bin/env python3
"""Surgical Q/A fixes for 19480101-御光話録（補）.txt."""

from __future__ import annotations

from pathlib import Path

from livros_qa_markers import count_gokowa_pt_questions, reflow_gokowa_pt
from qa_dialogue_annotation import parse_qa_turns, qa_turn_counts

ROOT = Path("/var/www/goshinsho")
OUT = ROOT / "reports/livros_trabalho/pt/19480101-御光話録（補）.txt"

REPLACEMENTS: list[tuple[str, str]] = [
    (
        "六月二十八日\n\n――人間は神様によって初めに地球上の一地域に作り出され、逐次各地に分散したものでしょうか、それとも地球上に広範囲に造り出されたものでしょうか。\n\n最初は一組の男女ができ、それから次第に殖えたのです。だから最初は血族結婚だった。「イモセ」という古い言葉は妹を妻にしたことであり、「吾妹子（わぎもこ）」とはこれを言うたものです。\n　しかし人間を作られたとき、人種はいろいろとお作りになった。また初めは土から作られたのでしょう。土人は黒土から作られ、それから赤土、白土というふうにね……人間は死ぬと土に還るのはその証拠です。もちろん人間だけではなく、物質はすべて土からできたんです。人間がどういうふうに作られたかはちょっと……\n\n\n――原日本人（天孫民族）は日本のいかなる地に造り出されたのでしょうか、あるいは地球上のどこかに造り出され日本に渡来したものでしょうか。\n\n天孫民族というのは漢族なのです。瓊瓊杵尊（ににぎのみこと）の系統で、この尊は漢の英雄です。これはユダヤではないかと思われます。ユダヤは昔十二種〔支〕族もあり、そのうち一種族だけ東方へ行ったと伝えられていますから、これが支那へ来てここで何かやろうとしたが、当時支那は栄えていて事を挙げることができず、そのうえユダヤは放浪性があり定住することがなかった。その中の一部が九州の高千穂に来て、\nUgaya Fukiaezu no Mikoto e depois se tornou o Imperador Jinmu. Desceram do alto da montanha, por isso são chamados de Netos Celestiais, mas não são puros. Há quem diga que viveram no Monte Fuji, mas isso provavelmente não é verdade.",
        """28 de junho

— Os seres humanos foram criados por Deus inicialmente numa única região da Terra e depois dispersos gradualmente por diversos lugares, ou foram criados em amplitude por toda a Terra?

No princípio surgiu um par de homem e mulher, e depois foram multiplicando-se. Por isso, no início havia casamento entre parentes de sangue. A palavra antiga "imose" significa tomar a irmã por esposa, e "wagimoko" (吾妹子) designa precisamente isso. No entanto, quando Deus criou os seres humanos, fez várias raças. Além disso, no princípio foram feitos de barro. Os negros foram feitos de barro preto, depois barro vermelho, barro branco, e assim por diante... O fato de os seres humanos, ao morrer, voltarem à terra é prova disso. Naturalmente, não só os seres humanos: toda a matéria foi feita da terra. Quanto a como exatamente os seres humanos foram criados, isso fica para depois...


— Onde foram criados os japoneses originários (povo Tenson)? Num lugar qualquer do Japão, ou em algum ponto da Terra de onde vieram ao Japão?

O povo Tenson é da etnia Han. É da linhagem de Ninigi no Mikoto; este Mikoto é um herói Han. Penso que possa ser judaico. Diz-se que antigamente havia doze tribos em Israel e que uma delas veio para o Oriente; esse grupo veio à China e tentou realizar algo, mas naquela época a China florescia e não puderam realizar o empreendimento, e além disso os judeus tinham natureza errante e não se fixavam. Parte deles veio a Takachiho, em Kyushu, e Ugaya Fukiaezu no Mikoto e depois se tornou o Imperador Jinmu. Desceram do alto da montanha, por isso são chamados Netos Celestiais, mas não são puros. Há quem diga que viveram no Monte Fuji, mas provavelmente não é verdade.""",
    ),
    (
        "Isso, veja bem, é porque os pais têm muito sangue tóxico. Por isso, a criança\n「待っていても駄目だから早く……しかし毒血はだんだん減りますからね。次に生まれる子はいいでしょう。……両方とも七日ですね。これには霊的なわけがありますよ。きっと七日に死んだ霊ですね。また、他人なら怨みの霊、怨んで死んだ霊であり、また先祖なら七日に死んだ祖霊で、非常に罪を重ねたので子孫にその罪を分担してもらうんです。ですから結局は人助けをして善徳を積んでいくことですね。」",
        """Isso, veja bem, é porque os pais têm muito sangue tóxico. Por isso, a criança não conseguiria crescer mesmo que esperassem; é melhor que parta cedo... Mas o sangue tóxico vai diminuindo gradualmente, por isso o próximo filho nascerá bem. ... Ambos morreram no sétimo dia, não é? Há uma razão espiritual nisso. Certamente são espíritos que morreram no sétimo dia. Se forem de outrem, são espíritos de rancor, espíritos que morreram com ressentimento; se forem ancestrais, são espíritos ancestrais que morreram no sétimo dia e, por terem acumulado muitíssimos pecados, fazem os descendentes partilharem essa culpa. Portanto, no fim das contas, trata-se de ajudar os outros e acumular mérito.""",
    ),
    (
        "――アザ、イボ、ホクロなどはなぜできるのでしょうか。\n\nアザには黒と赤の二種類ありますが、黒は怨みの霊で、それが霊に染みついて、霊界での浄化でも取りきれないうちに生まれた場合です。例えば肩を切られて死んだ場合、その怨みが向こうの肩へ行くんです。赤いアザのほうは自分が斬られたり槍で突かれたりしたが、やはり霊界で不浄化のまま再生したのですよ。ほくろは運命のしるしです。口の端のほくろは食いぼくろと言って食べ物に困らない。私は二つありますよ。首筋のは着ぼくろと言って着物に困らず、目の縁のは泣きぼくろと言いますね。それから鼻にほくろがあれば必ず陰部にもほくろがあります。こう言うと大先生はどうしてそれを調べたかと聞かれるかもしれませんがね。いぼも取れるのと取れないのとあります。やはりその人の運命のしるしですね。\n\n十一月二十八日",
        """— Por que aparecem manchas na pele (aza), verrugas (ibo) e sinais (hokuro)?

Há manchas pretas e vermelhas. As pretas vêm de espíritos de rancor que se impregnaram na alma e nasceram antes de serem completamente purificados no mundo espiritual. Por exemplo, se alguém morreu com o ombro cortado, o rancor vai para o ombro oposto. As vermelhas são de quem foi golpeado ou ferido com lança e renasceu sem purificação completa no mundo espiritual. Os sinais (hokuro) são marcas do destino. O sinal no canto da boca chama-se "sinal de comer" e indica que não faltará alimento; tenho dois. O do pescoço chama-se "sinal de vestir" e indica que não faltará roupa; o da borda dos olhos chama-se "sinal de chorar". Se há sinal no nariz, certamente há também na região genital. Se disser isto, talvez me perguntem como sei — bem... As verrugas também há as que se removem e as que não se removem; são marcas do destino da pessoa.

28 de novembro""",
    ),
]

INJECTION_JP = """――注射により死亡することが世間に多くありますが、これは注射薬の中にいわゆる毒素があるためでしょうか。

しかしね、薬の中に毒があるわけはないでしょう。毒なんか入っていれば当局でも許さないでしょうしね。今度の京都のジフテリア事件だって、大阪の日赤で作ったのだから毒なんかあるわけはない、平沢なんかいないでしょうから。……そこなんですよ。大体、薬というものは、私もよく言う通りないんですよ。もしあるとすれば米が薬です。米がなければ生きられないから。杉田玄白は「薬とは毒をもって毒を制するのである」と言っていますが、これは至言です。毒で体を弱らせて浄化を抑えるのが薬の効能です。……霊界の浄化力が強くなったので、注射液が体の一箇所へ寄ってくるのです。そのためにいろいろ障害が起きる。肝臓出血などはそれです。だから毒血が局部的に寄ってくると熱が出て苦しみが起きるのです。浄化が弱い時代は注射薬なんかは体全体に回り、それから局所へ寄ったのだが、今はそれが全体に回らないうちに寄ってしまうのです。

"""

INJECTION_PT = """— Há muitos casos de morte por injeção; isso se deve a chamadas toxinas dentro do medicamento injetável?

Não, não há veneno nos remédios. Se houvesse veneno, as autoridades não permitiriam. No recente caso de difteria em Kyoto, o soro foi feito pela Cruz Vermelha de Osaka, portanto não pode haver veneno — e Hirata não existe, não é? ... Aí está o ponto. Em geral, remédio, como sempre digo, não existe. Se algo é remédio, é o arroz: sem arroz não se vive. Sugita Genpaku disse: "Remédio é usar veneno para dominar veneno" — é uma sentença excelente. A função do remédio é enfraquecer o corpo com veneno e suprimir a purificação. ... Como a força purificadora do mundo espiritual se fortaleceu, a injeção concentra-se num ponto do corpo. Por isso surgem vários distúrbios; hemorragia hepática é disso. Quando o sangue tóxico se concentra localmente, surge febre e sofrimento. Na era em que a purificação era fraca, o medicamento injetável circulava por todo o corpo e depois se concentrava localmente; hoje concentra-se antes de circular por todo o corpo.

"""

TAIL_JP_PT = INJECTION_JP + """――注射直後、体が硬直することがよくございますが……

あれは注射を血管などへ打つ場合、その打つ場所が悪いのです。その結果、異物が心臓へ行くから死ぬんです。

――個人的または団体的な悪宣伝に対し、私どもは宗教人として、良い宣伝をもってこれに報いるべきでしょうか。

間違ったことに対する説明はいいですが、うっちゃっておいたほうがいいです。それに災いされて萎縮するようでは駄目ですよ。悪口を言われるのは結構です。悪口は浄化で、それでこちらの罪が消えるんです。

――悪い宣伝の結果、悪い支障が次々に起きてくる心配がありますが……

起きて結構です。これは今まで言われていたことと反対です。……大森時代、私は人から悪口を言われると笑ったものです。大本のお筆先に「悪く言われてよくなる仕組み」とありますが、いいことを言っています。いろいろな宗教がありますが、初めからよく言われた宗教はありません。世界的に広まっているキリスト教だって初めは十一人しか弟子がいなかったし、しかもキリストが死んで十年くらい経ってから覚え書きを書いた、それが今の『聖書』なんです。それからだんだんに広まってきたんです。釈迦だけは違うが、あれはインドの皇太子だったからです。天理教の中山みきだって二十何回留置場に入れられ、四回検事局送りになったのです。ともかく最初は悪く言われるものです。もっとも今でも天理教を悪く言う人はありますが。

――悪宣伝に対して言い訳をすることはいかがでしょうか。

いけない、いけない。言い訳を言うようでは野暮ですよ。悪口を笑って通せれば一段できた証拠です。何か勝負事のようなことでも負けたほうがよい。勝った場合には「あいつは負けたんで俺を怨んでいないか」などと思うが、負ければこんなことはない。だから結局人間は怨みの霊が来ないように、感謝の霊が来るようにすることが肝心です。決して人の怨みを買ってはいけない。これくらい霊的に損をすることはないんです。

――「恒産なき者は恒心なし」との格言がありますが、現在の世相においても当てはまるものでございましょうか。

これは当てはまります。どうしても人間は貧苦するとろくな考えがなく、ついごまかしたりする。だから生活の心配のないところまで行かねばいけない。宗教を信じるならそこまで行かねばならない。今までの宗教は体を救えなかったのです。例えば病気で苦しんでいて感謝なんか出るはずはないんです。あれは自己を偽っているのです。……今までの宗教でいう「さとり」とは「諦め」の字を使い諦めですが、私のは「覚」であり、知るさとりです。

――神国思想はあまり口に出さぬようにとのお言葉でございましたが、大先生様の御神格について会員にはどのようにお話ししたらよろしいでしょうか。

神国思想はいけません。……私のことは思った通りを話したらいいですよ。

――日本は神国だから大先生様がお生まれになられたということは……

そんなことはありません。神国思想と私とは関係ありません。……これは難しいところで、大切なのは私の仕事を考えることです。例えば今までは人間の生命はどうにもできなかった。私はそれを延ばすことができるのです。だからその「事実」ですよ。今までもキリストの再臨なんていうのが時々出たが、本当の「事実」がない。三十年ほど前にもインドにサンダーシングという三十歳くらいの男が水の上を渡ったりしたので、キリストの再臨とまで称されたが若死にしてしまいました。しかし水を渡ったりしたって人間に何の益もない。単なる興行師にすぎない。つまり病気が治ったり、貧苦が解決したりなど、実際の効果がなければ駄目です。私は言うのですが、釈迦やキリストも偉いが人の病気を治せなかった。キリスト自身は多少治したりしたが弟子にはその力がなかった。釈迦の死だって行き倒れです。釈迦が亡くなられたとき獣が集まって来て泣いたなどというのは後からの付け足しです。

――患者を御浄霊する場合、霊的動作を表わすことがございますが、その先生によりその土地により相違があるようですが、これはなぜでしょうか。

これは無論ありますよ。憑いている霊がその先生より上の場合と下の場合があり、上の場合には「お前さんには言えない」と言うし、下の場合には「お前さんは偉いから話をする」と言う。狐なんか殊にそうです。結局それは光の多い人に頭を下げるわけです。……霊が浮くというのは苦しいから浮いてくる場合と、また霊によっては憑いてからまだ短時日だと浮きやすいということもあります。土地ということにはあまり関係ないが、土地により霊懸かりの多いのと少ないのとはあります。狐の親玉なんかがいればその子分もその辺にたくさんいますから。

――よくその先生に力があるからだとか、あるいはその先生にそんな霊が憑いているから同じようなのが集まるのだとも聞きますが……

先生によることはあります。が、その人により霊が集まるということはないですね。

――教導所で治り難い患者が幾人も来ることがありますが、これはその教導師が何か自己反省すべき点があるためでしょうか。あるいは何か他に神様の思し召しがあるのでしょうか。

神様の思し召しということはない。すべてを救われるのが神様の思し召しであって、思し召しで治さないなんてことはない。
　昨日も話したことなんですが「軍神」なんてことはないのです。今度の戦犯の判決なんかまだ軽すぎます。戦犯の犯した罪に比べれば平沢なんかは蚤の糞みたいなものです。マッカーサー元帥が「これを機会に戦争をなくしてしまいたい」と言っているのは本当です。こういう点の判断が日本人はどうもいけない。同情してしまって罪を軽くしようとする。……で、軍神というふうに人を殺すことを手伝う神なんか正しい神ではない。
　治りにくいというのは教導師の頭の働きが悪いのです。急所を当てれば治りが早いのです。外れていては治らない。中には体全体やればどれか当たるだろうといった調子で機関銃式にする人があるが、それでは駄目です。ほんの小さな毒結のために全身的に発熱することがあるが、そのときその毒結をやればたちまち全身的に解熱する。

――着物を着たままでも急所は分かりましょうか。

着たままでも分かりますよ。どの病気はどこをやるか、その基準を知ることも大切です。例えば腹の悪い人は背中からやるだけで治ってしまう。
　御守護をいただくには混じり気があったら駄目です。

――今まで神道だった人がお道に入られた場合、御先祖はどのようにお祀りすべきでしょうか。

お祀りはそのままでよろしい。先祖の代から神道ならいいが、途中から仏立講みたいに過去帳にすると先祖は怒りますよ。あれは非常に間違っている。霊友会では他人の先祖をよく祀るがあれはいいですね。そういう設備もあったほうがよい。私の所でも他人の仏をだいぶ祀っています。

――土蔵の白蛇を殺しましたが、これは人間より上でしょうか。また、祀り方はいかがいたすべきでしょうか。また、何年くらい祀ってやるべきでしょうか。

あのね、蛇はどんなのでも人間より下です。同様にどんな立派な稲荷でも人間より下です。"""

TAIL_PT = INJECTION_PT + """— Logo após a injeção, o corpo frequentemente fica rígido...

Isso ocorre quando a injeção é aplicada na veia ou semelhante: o local da punção é inadequado. O corpo estranho vai ao coração e a pessoa morre.

— Diante de más propagandas pessoais ou coletivas, devemos, como religiosos, retribuir com boa propaganda?

Explicar o que está errado é bom, mas é melhor deixar passar. Se ficarem amedrontados por serem amaldiçoados, não servem. Que falem mal — está bem. Más palavras são purificação, e com isso nossos pecados se dissolvem.

— Preocupa-me que, por causa de más propagandas, surjam sucessivamente más consequências...

Que surjam, está bem. Isto é o oposto do que se dizia antes. ... Na era de Omori, quando falavam mal de mim, eu ria. No escritório do Oomoto há "o mecanismo pelo qual ser mal falado torna-se benefício" — diz coisa boa. Há várias religiões, mas nenhuma foi bem falada desde o princípio. O cristianismo, que se espalhou pelo mundo, no início tinha apenas onze discípulos; e foi cerca de dez anos depois da morte de Cristo que escreveram memorandos — isso é a Bíblia de hoje. Depois foi se espalhando gradualmente. Só Buda é diferente, pois era príncipe da Índia. Nakayama Miki, da Tenri-kyo, foi detida mais de vinte vezes e enviada quatro vezes ao Ministério Público. De qualquer modo, no princípio sempre se é mal falado. Ainda hoje há quem fale mal da Tenri-kyo.

— O que acha de dar desculpas diante de más propagandas?

Não, não. Quem dá desculpas é tolo. Se rir das más palavras e passar adiante, isso prova que avançou um degrau. Em qualquer disputa, às vezes é melhor perder. Se ganhar, pensa: "Será que aquele não me guarda rancor por ter perdido?" Se perder, isso não acontece. Portanto, o essencial é fazer com que venham espíritos de gratidão e não espíritos de rancor. Nunca se deve comprar o rancor alheio — espiritualmente não há perda maior.

— Há o provérbio "Quem não tem patrimônio fixo não tem constância de coração". Isso ainda se aplica ao mundo de hoje?

Sim, aplica-se. Quando o ser humano vive na pobreza, deixa de pensar retamente e acaba enganando. Por isso é preciso chegar a um ponto em que não se preocupe com a vida. Quem crê numa religião deve chegar a esse ponto. As religiões até agora não salvavam o corpo. Quem sofre de doença não pode sentir gratidão — isso é fingir. ... O "satori" das religiões antigas usa o caractere de resignação; o meu é "despertar", satori de conhecer.

— Disse-se para não falar muito da ideia de nação divina; como devemos falar aos membros sobre a divindade do Grande Mestre?

A ideia de nação divina não serve. ... Quanto a mim, basta dizer o que pensarem.

— Seria porque o Japão é nação divina que o Grande Mestre nasceu...

Não é nada disso. A ideia de nação divina não tem relação comigo. ... Isto é difícil; o essencial é pensar no meu trabalho. Até agora não se podia prolongar a vida humana; eu posso prolongá-la. Esse é o "fato". Já apareceram vezes falsos "retornos de Cristo", sem fato verdadeiro. Há cerca de trinta anos, na Índia, um homem de uns trinta anos chamado Sundar Singh andou sobre a água e chegou a ser chamado retorno de Cristo, mas morreu jovem. Andar sobre a água não beneficia a humanidade; é mero showman. Sem efeito real — curar doenças, resolver pobreza — não serve. Digo: Buda e Cristo são grandiosos, mas não curavam as doenças alheias. Cristo curou um pouco, mas os discípulos não tinham esse poder. Buda morreu na estrada. Dizem que quando Buda morreu os animais vieram chorar — isso foi acrescentado depois.

— Ao purificar pacientes, às vezes manifestam-se movimentos espirituais que diferem conforme o professor ou a região; por quê?

Naturalmente há diferença. Se o espírito possuidor está acima do professor, diz "não posso falar com você"; se está abaixo, diz "você é grandioso, falarei". As raposas especialmente. No fim, inclinam-se diante de quem tem mais luz. ... Flutuar é porque sofrem, ou porque o espírito acabou de possuir e flutua facilmente. A terra importa pouco, mas há regiões com mais ou menos espíritos possuidores. Se há raposa-matriz, há muitos subordinados por perto.

— Ouvi dizer que certo professor tem força, ou que espíritos semelhantes se reúnem porque tal espírito possui o professor...

Depende do professor, sim; mas espíritos não se reúnem por causa da pessoa.

— Vários pacientes difíceis de curar vêm ao centro de ensino; isso se deve a algo que o instrutor deva refletir, ou à vontade de Deus?

Não há "vontade de Deus" nesse sentido. Salvar a todos é a vontade de Deus; não curar não faz parte dela.
Ontem também falei: não existe "deus da guerra". A sentença dos criminosos de guerra ainda é leve demais; comparado aos pecados deles, Hirata é como fezes de pulga. MacArthur disse que quer aproveitar esta ocasião para acabar com a guerra — é verdade. Os japoneses julgam mal nesses pontos, compadecendo-se e aliviando a culpa. ... Deus que ajuda a matar pessoas não é deus correto.
"Difícil de curar" significa que a cabeça do instrutor funciona mal. Se acertar o ponto vital, cura rápido; se errar, não cura. Há quem faça estilo metralhadora pelo corpo todo pensando que algum ponto acertará — não serve. Por uma pequena concentração de veneno pode haver febre generalizada; se tratar esse ponto, a febre desce de imediato.

— Com o quimono vestido, ainda se identificam os pontos vitais?

Com o quimono vestido, identifica-se. Saber qual doença tratar em qual lugar também é essencial. Quem tem estômago fraco, por exemplo, cura-se fazendo nas costas.
Para receber Omamori (Ohikari) de proteção, não pode haver mistura.

— Quando alguém que era xintoísta entra neste Caminho, como consagrar os ancestrais?

A consagração pode permanecer como está. Se a família era xintoísta de geração em geração, está bem; se no meio do caminho registra ancestrais num livro como num budismo laico, os ancestrais se iram — isso é gravíssimo erro. A Reiyu-kai consagra bem os ancestrais alheios — isso é bom; convém ter essa estrutura. Eu também consagro muitos budas alheios.

— Matei a cobra branca do celeiro; ela está acima do ser humano? Como consagrá-la? Por quantos anos?

Veja bem: cobra, seja qual for, está abaixo do ser humano. Do mesmo modo, por mais excelente que seja um Inari, está abaixo do ser humano."""

REPLACEMENTS.append((TAIL_JP_PT, TAIL_PT))

REPLACEMENTS.extend([
    (
        "Aqui está a tradução:\n\nSeguem abaixo. Houve um caso",
        "Houve um caso",
    ),
    (
        "-- Medidas quando",
        "— Medidas quando",
    ),
    (
        "-- O mundo espiritual",
        "— O mundo espiritual",
    ),
    (
        "-- O irmão mais velho",
        "— O irmão mais velho",
    ),
    (
        "-- Vossa Senhoria disse",
        "— Vossa Senhoria disse",
    ),
    (
        "-- Desde que nos tornamos",
        "— Desde que nos tornamos",
    ),
    (
        "-- O que acha de despir",
        "— O que acha de despir",
    ),
    (
        "-- E nos casos de apendicite",
        "— E nos casos de apendicite",
    ),
    (
        "-- Pode-se fazer o Johrei",
        "— Pode-se fazer o Johrei",
    ),
    (
        "-- Não é preciso se preocupar",
        "— Não é preciso se preocupar",
    ),
    (
        "-- E quanto a coisas como asma",
        "— E quanto a coisas como asma",
    ),
    (
        "-- Apelar para Kannon-Sama",
        "— Apelar para Kannon-Sama",
    ),
    (
        "-- Muitas pessoas no mundo",
        "— Muitas pessoas no mundo",
    ),
    (
        "-- Acredito que o espírito",
        "— Acredito que o espírito",
    ),
    (
        "-- De que nacionalidade",
        "— De que nacionalidade",
    ),
    (
        "-- Embora se fale em igualdade",
        "— Embora se fale em igualdade",
    ),
    (
        "-- Durante o funeral",
        "— Durante o funeral",
    ),
    (
        "-- Isso é oferecido a Deus",
        "— Isso é oferecido a Deus",
    ),
    (
        "-- Segundo a história",
        "— Segundo a história",
    ),
    (
        "— Ao perguntar ao Mestre,\n (1) Devo ouvir em silêncio até o fim?\n (2) Se não for possível expressar completamente sem acrescentar palavras, como devo proceder?\n (3) Se não conseguir compreender sem perguntar repetidamente, como devo proceder?",
        "— Ao perguntar ao Mestre: (1) devo ouvir em silêncio até o fim? (2) se não for possível expressar completamente sem acrescentar palavras, como devo proceder? (3) se não conseguir compreender sem perguntar repetidamente, como devo proceder?",
    ),
    (
        "――Mas afastar-se parece solitário...",
        "— Mas afastar-se parece solitário; isso não é inevitável?",
    ),
    (
        "— Ouvi do senhor Okaniwa.",
        "— Ouvi do senhor Okaniwa que Jesus acreditava ser o Cristo por vontade proposital de Deus; isso procede?",
    ),
    (
        "— Maria concebeu Jesus virgem.\nDizem que isso deu origem ao caos...",
        "— Maria concebeu Jesus virgem; dizem que isso deu origem ao caos... isso procede?",
    ),
])


def main() -> None:
    text = OUT.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if old not in text:
            raise SystemExit(f"PATCH NOT FOUND:\n{old[:120]}...")
        text = text.replace(old, new, 1)

    OUT.write_text(text, encoding="utf-8")

    jp = (ROOT / "reports/livros_trabalho/jp/19480101-御光話録（補）.txt").read_text(
        encoding="utf-8"
    )
    jq = qa_turn_counts(parse_qa_turns(jp, lang="jp", profile="gokowa_roku_qa"))[0]
    pq = count_gokowa_pt_questions(reflow_gokowa_pt(text))
    print(f"JP={jq} PT={pq} diff={pq - jq}")
    if jq != pq:
        raise SystemExit("Q/A mismatch remains")


if __name__ == "__main__":
    main()
