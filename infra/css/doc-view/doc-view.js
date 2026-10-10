//#region node_modules/marked/lib/marked.esm.js
function e() {
	return {
		async: !1,
		breaks: !1,
		extensions: null,
		gfm: !0,
		hooks: null,
		pedantic: !1,
		renderer: null,
		silent: !1,
		tokenizer: null,
		walkTokens: null
	};
}
var t = e();
function n(e) {
	t = e;
}
var r = { exec: () => null };
function i(e) {
	let t = [];
	return (n) => {
		let r = Math.max(0, Math.min(3, n - 1)), i = t[r];
		return i || (i = e(r), t[r] = i), i;
	};
}
function a(e, t = "") {
	let n = typeof e == "string" ? e : e.source, r = {
		replace: (e, t) => {
			let i = typeof t == "string" ? t : t.source;
			return i = i.replace(s.caret, "$1"), n = n.replace(e, i), r;
		},
		getRegex: () => new RegExp(n, t)
	};
	return r;
}
var o = ((e = "") => {
	try {
		return !!RegExp("(?<=1)(?<!1)" + e);
	} catch {
		return !1;
	}
})(), s = {
	codeRemoveIndent: /^(?: {0,3}\t| {1,4})/gm,
	outputLinkReplace: /\\([\[\]])/g,
	indentCodeCompensation: /^(\s+)(?:```)/,
	beginningSpace: /^\s+/,
	endingHash: /#$/,
	startingSpaceChar: /^ /,
	endingSpaceChar: / $/,
	endingSpaceTabChar: /[ \t]$/,
	nonSpaceChar: /[^ ]/,
	newLineCharGlobal: /\n/g,
	tabCharGlobal: /\t/g,
	leadingSpaceTab: /^[ \t]+/,
	multipleSpaceGlobal: /\s+/g,
	blankLine: /^[ \t]*$/,
	doubleBlankLine: /\n[ \t]*\n[ \t]*$/,
	blockquoteStart: /^ {0,3}>/,
	blockquoteSetextReplace: /\n {0,3}((?:=+|-+) *)(?=\n|$)/g,
	blockquoteSetextReplace2: /^ {0,3}>[ \t]?/gm,
	listReplaceNesting: /^ {1,4}(?=( {4})*[^ ])/g,
	listIsTask: /^\[[ xX]\] +\S/,
	listReplaceTask: /^\[[ xX]\] +/,
	listTaskCheckbox: /\[[ xX]\]/,
	anyLine: /\n.*\n/,
	hrefBrackets: /^<(.*)>$/,
	tableDelimiter: /[:|]/,
	tableAlignChars: /^\||\| *$/g,
	tableRowBlankLine: /\n[ \t]*$/,
	tableAlignRight: /^ *-+: *$/,
	tableAlignCenter: /^ *:-+: *$/,
	tableAlignLeft: /^ *:-+ *$/,
	startATag: /^<a /i,
	endATag: /^<\/a>/i,
	startPreScriptTag: /^<(pre|code|kbd|script)(\s|>)/i,
	endPreScriptTag: /^<\/(pre|code|kbd|script)(\s|>)/i,
	startAngleBracket: /^</,
	endAngleBracket: />$/,
	pedanticHrefTitle: /^([^'"]*[^\s])\s+(['"])(.*)\2/,
	unicodeAlphaNumeric: /[\p{L}\p{N}]/u,
	numericCharacterReference: /&#(?:(\d{1,7})|[Xx]([A-Fa-f0-9]{1,6}));/g,
	escapeTest: /[&<>"']/,
	escapeReplace: /[&<>"']/g,
	escapeTestNoEncode: /[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)/,
	escapeReplaceNoEncode: /[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)/g,
	caret: /(^|[^\[])\^/g,
	percentDecode: /%25/g,
	findPipe: /\|/g,
	splitPipe: / \|/,
	slashPipe: /\\\|/g,
	carriageReturn: /\r\n|\r/g,
	spaceLine: /^ +$/gm,
	notSpaceStart: /^\S*/,
	endingNewline: /\n$/,
	listItemRegex: (e) => RegExp(`^( {0,3}${e})((?:[	 ][^\\n]*)?(?:\\n|$))`),
	nextBulletRegex: i((e) => RegExp(`^ {0,${e}}(?:[*+-]|\\d{1,9}[.)])((?:[ 	][^\\n]*)?(?:\\n|$))`)),
	hrRegex: i((e) => RegExp(`^ {0,${e}}((?:-[ 	]*){3,}|(?:_[ 	]*){3,}|(?:\\*[ 	]*){3,})(?:\\n+|$)`)),
	fencesBeginRegex: i((e) => RegExp(`^ {0,${e}}(?:\`\`\`|~~~)`)),
	headingBeginRegex: i((e) => RegExp(`^ {0,${e}}#`)),
	htmlBeginRegex: i((e) => RegExp(`^ {0,${e}}(?:</?(?:${_})(?: +|$|/?>)|<(?:script|pre|style|textarea|!--))`, "i")),
	blockquoteBeginRegex: i((e) => RegExp(`^ {0,${e}}>`))
}, c = /^(?:[ \t]*(?:\n|$))+/, l = /^((?: {4}| {0,3}\t)[^\n]+(?:\n(?:[ \t]*(?:\n|$))*)?)+/, u = /^ {0,3}(`{3,}(?=[^`\n]*(?:\n|$))|~{3,})([^\n]*)(?:\n|$)(?:|([\s\S]*?)(?:\n|$))(?: {0,3}\1[~`]* *(?=\n|$)|$)/, d = /^ {0,3}((?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)/, f = /^ {0,3}(#{1,6})(?=\s|$)(.*)(?:\n+|$)/, p = / {0,3}(?:[*+-]|\d{1,9}[.)])/, m = /^(?!bull |blockCode|fences|blockquote|heading|html|table)((?:.|\n(?!\s*?\n|bull |fences|blockquote|heading|hr|html|table))+?)\n {0,3}(=+|-+) *(?:\n+|$)/, ee = a(m).replace(/bull/g, p).replace(/blockCode/g, /(?: {4}| {0,3}\t)/).replace(/fences/g, / {0,3}(?:`{3,}|~{3,})/).replace(/blockquote/g, / {0,3}>/).replace(/heading/g, / {0,3}#{1,6}(?:\s|$)/).replace(/hr/g, / {0,3}(?:(?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)/).replace(/html/g, / {0,3}<[^\n>]+>\n/).replace(/\|table/g, "").getRegex(), te = a(m).replace(/bull/g, p).replace(/blockCode/g, /(?: {4}| {0,3}\t)/).replace(/fences/g, / {0,3}(?:`{3,}|~{3,})/).replace(/blockquote/g, / {0,3}>/).replace(/heading/g, / {0,3}#{1,6}(?:\s|$)/).replace(/hr/g, / {0,3}(?:(?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)/).replace(/html/g, / {0,3}<[^\n>]+>\n/).replace(/table/g, / {0,3}\|?(?:[:\- ]*\|)+[\:\- ]*\n/).getRegex(), h = /^([^\n]+(?:\n(?!hr|heading|lheading|blockquote|fences|list|html|table|[ \t]+\n)[^\n]+)*)/, ne = /^[^\n]+/, re = /(?!\s*\])(?:\\[\s\S]|[^\[\]\\])+/, g = a(/^ {0,3}\[(label)\]: *(?:\n[ \t]*)?([^<\s][^\s]*|<.*?>)(?:(?: +(?:\n[ \t]*)?| *\n[ \t]*)(title))? *(?:\n+|$)/).replace("label", re).replace("title", /(?:"(?:\\"?|[^"\\])*"|'[^'\n]*(?:\n[^'\n]+)*\n?'|\([^()]*\))/).getRegex(), ie = a(/^(bull)([ \t][^\n]*?)?(?:\n|$)/).replace(/bull/g, p).getRegex(), _ = "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|meta|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul", v = /<!--(?:-?>|[\s\S]*?(?:-->|$))/, ae = a("^ {0,3}(?:<(script|pre|style|textarea)[\\s>][\\s\\S]*?(?:</\\1>[^\\n]*\\n*|$)|comment[^\\n]*(\\n+|$)|<\\?[\\s\\S]*?(?:\\?>[^\\n]*\\n*|$)|<![A-Z][\\s\\S]*?(?:>[^\\n]*\\n*|$)|<!\\[CDATA\\[[\\s\\S]*?(?:\\]\\]>[^\\n]*\\n*|$)|</?(tag)(?: +|\\n|/?>)[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$)|<(?!script|pre|style|textarea)([a-z][a-z0-9-]*)(?:attribute)*? */?>(?=[ \\t]*(?:\\n|$))[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$)|</(?!script|pre|style|textarea)[a-z][a-z0-9-]*\\s*>(?=[ \\t]*(?:\\n|$))[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$))", "i").replace("comment", v).replace("tag", _).replace("attribute", / +[a-zA-Z:_][\w.:-]*(?: *= *"[^"\n]*"| *= *'[^'\n]*'| *= *[^\s"'=<>`]+)?/).getRegex(), y = (e) => a(h).replace("hr", d).replace("heading", " {0,3}#{1,6}(?:\\s|$)").replace("|lheading", "").replace("|table", "").replace("blockquote", " {0,3}>").replace("fences", " {0,3}(?:`{3,}(?=[^`\\n]*(?:\\n|$))|~~~)[^\\n]*(?:\\n|$)").replace("list", e).replace("html", "</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag", _).getRegex(), b = y(/ {0,3}(?:[*+-]|1[.)])[ \t]+[^ \t\n]/), oe = y(/ {0,3}(?:[*+-]|\d{1,9}[.)])(?:[ \t]|\n|$)/), se = {
	blockquote: a(/^( {0,3}> ?(paragraph|[^\n]*)(?:\n|$))+/).replace("paragraph", oe).getRegex(),
	code: l,
	def: g,
	fences: u,
	heading: f,
	hr: d,
	html: ae,
	lheading: ee,
	list: ie,
	newline: c,
	paragraph: b,
	table: r,
	text: ne
}, ce = a("^ *([^\\n ].*)\\n {0,3}((?:\\| *)?:?-+:? *(?:\\| *:?-+:? *)*(?:\\| *)?)(?:\\n((?:(?! *\\n|hr|heading|blockquote|code|fences|list|html).*(?:\\n|$))*)\\n*|$)").replace("hr", d).replace("heading", " {0,3}#{1,6}(?:\\s|$)").replace("blockquote", " {0,3}>").replace("code", "(?: {4}| {0,3}	)[^\\n]").replace("fences", " {0,3}(?:`{3,}(?=[^`\\n]*(?:\\n|$))|~~~)[^\\n]*(?:\\n|$)").replace("list", " {0,3}(?:[*+-]|1[.)])[ \\t]").replace("html", "</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag", _).getRegex(), le = {
	...se,
	lheading: te,
	table: ce,
	paragraph: a(h).replace("hr", d).replace("heading", " {0,3}#{1,6}(?:\\s|$)").replace("|lheading", "").replace("table", ce).replace("blockquote", " {0,3}>").replace("fences", " {0,3}(?:`{3,}(?=[^`\\n]*(?:\\n|$))|~~~)[^\\n]*(?:\\n|$)").replace("list", " {0,3}(?:[*+-]|1[.)])[ \\t]+[^ \\t\\n]").replace("html", "</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag", _).getRegex()
}, ue = {
	...se,
	html: a("^ *(?:comment *(?:\\n|\\s*$)|<(tag)[\\s\\S]+?</\\1> *(?:\\n{2,}|\\s*$)|<tag(?:\"[^\"]*\"|'[^']*'|\\s[^'\"/>\\s]*)*?/?> *(?:\\n{2,}|\\s*$))").replace("comment", v).replace(/tag/g, "(?!(?:a|em|strong|small|s|cite|q|dfn|abbr|data|time|code|var|samp|kbd|sub|sup|i|b|u|mark|ruby|rt|rp|bdi|bdo|span|br|wbr|ins|del|img)\\b)\\w+(?!:|[^\\w\\s@]*@)\\b").getRegex(),
	def: /^ *\[([^\]]+)\]: *<?([^\s>]+)>?(?: +(["(][^\n]+[")]))? *(?:\n+|$)/,
	heading: /^(#{1,6})(.*)(?:\n+|$)/,
	fences: r,
	lheading: /^(.+?)\n {0,3}(=+|-+) *(?:\n+|$)/,
	paragraph: a(h).replace("hr", d).replace("heading", " *#{1,6} *[^\n]").replace("lheading", ee).replace("|table", "").replace("blockquote", " {0,3}>").replace("|fences", "").replace("|list", "").replace("|html", "").replace("|tag", "").getRegex()
}, de = /^\\([!"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])/, fe = /^(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)/, pe = /^( {2,}|\\)\n(?!\s*$)[ \t]*/, me = /^(`+|[^`])(?:(?= {2,}\n)|[\s\S]*?(?:(?=[\\<!\[`*_]|\b_|$)|[^ ](?= {2,}\n)))/, x = /[\p{P}\p{S}]/u, he = /[\s\p{P}\p{S}]/u, ge = /[^\s\p{P}\p{S}]/u, _e = a(/^((?![*_])punctSpace)/, "u").replace(/punctSpace/g, he).getRegex(), S = /[\p{Pi}\p{Ps}"']/u, ve = /(?!~)[\p{P}\p{S}]/u, ye = /(?!~)[\s\p{P}\p{S}]/u, be = /(?:[^\s\p{P}\p{S}]|~)/u, xe = a(/link|precode-code|html/, "g").replace("link", /\[(?:[^\[\]`]|(?<a>`+)[^`]+\k<a>(?!`))*?\]\((?:\\[\s\S]|[^\\\(\)]|\((?:\\[\s\S]|[^\\\(\)])*\))*\)/).replace("precode-", o ? "(?<!`)()" : "(^^|[^`])").replace("code", /(?<b>`+)[^`]+\k<b>(?!`)/).replace("html", /<(?! )[^<>]*?>/).getRegex(), Se = /^(?:\*+(?:((?!\*)punct)|([^\s*]))?)|^_+(?:((?!_)punct)|([^\s_]))?/, Ce = a(Se, "u").replace(/punct/g, x).getRegex(), we = a(Se, "u").replace(/punct/g, ve).getRegex(), Te = a(/^(?:\*+(?:((?!\*)(?!openQuote)punct)|([^\s*]))?)|^_+(?:((?!_)(?!openQuote)punct)|([^\s_]))?/, "u").replace(/openQuote/g, S).replace(/punct/g, x).getRegex(), Ee = "^[^_*]*?__[^_*]*?\\*[^_*]*?(?=__)|[^*]+(?=[^*])|(?!\\*)punct(\\*+)(?=[\\s]|$)|notPunctSpace(\\*+)(?!\\*)(?=punctSpace|$)|(?!\\*)punctSpace(\\*+)(?=notPunctSpace)|[\\s](\\*+)(?!\\*)(?=punct)|(?!\\*)punct(\\*+)(?!\\*)(?=punct)|notPunctSpace(\\*+)(?=notPunctSpace)", C = a(Ee, "gu").replace(/notPunctSpace/g, ge).replace(/punctSpace/g, he).replace(/punct/g, x).getRegex(), De = a(Ee, "gu").replace(/notPunctSpace/g, be).replace(/punctSpace/g, ye).replace(/punct/g, ve).getRegex(), w = a("^[^_*]*?__[^_*]*?\\*[^_*]*?(?=__)|[^*]+(?=[^*])|(?!\\*)punct(\\*+)(?=[\\s]|$)|notPunctSpace(\\*+)(?!\\*)(?=punctSpace|$)|(?!\\*)[\\s](\\*+)(?=notPunctSpace)|[\\s](\\*+)(?!\\*)(?=punct)|(?!\\*)punct(\\*+)(?!\\*)(?=punct)|(?:(?!\\*)punct|notPunctSpace)(\\*+)(?!\\*)(?=notPunctSpace)", "gu").replace(/notPunctSpace/g, ge).replace(/punctSpace/g, he).replace(/punct/g, x).getRegex(), Oe = a("^[^_*]*?\\*\\*[^_*]*?_[^_*]*?(?=\\*\\*)|[^_]+(?=[^_])|(?!_)punct(_+)(?=[\\s]|$)|notPunctSpace(_+)(?!_)(?=punctSpace|$)|(?!_)punctSpace(_+)(?=notPunctSpace)|[\\s](_+)(?!_)(?=punct)|(?!_)punct(_+)(?!_)(?=punct)", "gu").replace(/notPunctSpace/g, ge).replace(/punctSpace/g, he).replace(/punct/g, x).getRegex(), T = a("^[^_*]*?\\*\\*[^_*]*?_[^_*]*?(?=\\*\\*)|[^_]+(?=[^_])|(?!_)punct(_+)(?=[\\s]|$)|notPunctSpace(_+)(?!_)(?=punctSpace|$)|(?!_)[\\s](_+)(?=notPunctSpace)|[\\s](_+)(?!_)(?=punct)|(?!_)punct(_+)(?!_)(?=punct)|(?:(?!_)punct|notPunctSpace)(_+)(?!_)(?=notPunctSpace)", "gu").replace(/notPunctSpace/g, ge).replace(/punctSpace/g, he).replace(/punct/g, x).getRegex(), ke = a(/^~~?(?:((?!~)punct)|[^\s~])/, "u").replace(/punct/g, x).getRegex(), Ae = a("^[^~]+(?=[^~])|(?!~)punct(~~?)(?=[\\s]|$)|notPunctSpace(~~?)(?!~)(?=punctSpace|$)|(?!~)punctSpace(~~?)(?=notPunctSpace)|[\\s](~~?)(?!~)(?=punct)|(?!~)punct(~~?)(?!~)(?=punct)|notPunctSpace(~~?)(?=notPunctSpace)", "gu").replace(/notPunctSpace/g, ge).replace(/punctSpace/g, he).replace(/punct/g, x).getRegex(), E = a(/\\(punct)/, "gu").replace(/punct/g, x).getRegex(), je = a(/^<(scheme:[^\s\x00-\x1f<>]*|email)>/).replace("scheme", /[a-zA-Z][a-zA-Z0-9+.-]{1,31}/).replace("email", /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+(@)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+(?![-_])/).getRegex(), Me = a(v).replace("(?:-->|$)", "-->").getRegex(), Ne = a("^comment|^</[a-zA-Z][a-zA-Z0-9-]*\\s*>|^<[a-zA-Z][a-zA-Z0-9-]*(?:attribute)*?\\s*/?>|^<\\?[\\s\\S]*?\\?>|^<![a-zA-Z]+\\s[\\s\\S]*?>|^<!\\[CDATA\\[[\\s\\S]*?\\]\\]>").replace("comment", Me).replace("attribute", /\s+[a-zA-Z:_][\w.:-]*(?:\s*=\s*"[^"]*"|\s*=\s*'[^']*'|\s*=\s*[^\s"'=<>`]+)?/).getRegex(), Pe = /\[(?:\\[\s\S]|[^\[\]\\])*\]/, D = a(/(?:\[(?:brackets|\\[\s\S]|[^\[\]\\])*\]|\\[\s\S]|`+(?!`)[^`]*?`+(?!`)|``+(?=\])|[^\[\]\\`])*?/).replace("brackets", Pe).getRegex(), Fe = a(/^!?\[(label)\]\([ \t\n]*(href)(?:(?:[ \t]+(?:\n[ \t]*)?|\n[ \t]*)(title))?[ \t\n]*\)/).replace("label", D).replace("href", /<(?:\\.|[^\n<>\\])+>|[^ \t\n\x00-\x1f]+|(?=\))/).replace("title", /"(?:\\"?|[^"\\])*"|'(?:\\'?|[^'\\])*'|\((?:\\\)?|[^)\\])*\)/).getRegex(), O = a(/^!?\[(label)\]\[(ref)\]/).replace("label", D).replace("ref", re).getRegex(), Ie = a(/^!?\[(ref)\](?:\[\])?/).replace("ref", re).getRegex(), Le = /(?!\s*\])(?:\\[\s\S]|[^\[\]\\]){1,999}/, Re = a(/(?:[^\[\]\\`]*(?:\[(?:brackets|\\[\s\S]|[^\[\]\\])*\]|\\[\s\S]|`+(?!`)[^`]*?`+(?!`)|``+(?=\]))){0,999}?[^\[\]\\`]*?/).replace("brackets", Pe).getRegex(), ze = a("reflink|nolink(?!\\()", "g").replace("reflink", a(/^!?\[(label)\]\[(ref)\]/).replace("label", Re).replace("ref", Le).getRegex()).replace("nolink", a(/^!?\[(ref)\](?:\[\])?/).replace("ref", Le).getRegex()).getRegex(), k = /[hH][tT][tT][pP][sS]?|[fF][tT][pP]/, Be = a(/(?:mailto:email|xmpp:email(?:\/[A-Za-z0-9@.]+)?)/).replace(/email/g, /[A-Za-z0-9._+-]+@[a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]*[a-zA-Z0-9])+(?![\w-])/).getRegex(), Ve = {
	_backpedal: r,
	anyPunctuation: E,
	autolink: je,
	blockSkip: xe,
	br: pe,
	code: fe,
	del: r,
	delLDelim: r,
	delRDelim: r,
	emStrongLDelim: Ce,
	emStrongRDelimAst: C,
	emStrongRDelimUnd: Oe,
	escape: de,
	link: Fe,
	nolink: Ie,
	punctuation: _e,
	reflink: O,
	reflinkSearch: ze,
	tag: Ne,
	text: me,
	url: r
}, He = {
	...Ve,
	emStrongLDelim: Te,
	emStrongRDelimAst: w,
	emStrongRDelimUnd: T,
	link: a(/^!?\[(label)\]\((.*?)\)/).replace("label", D).getRegex(),
	reflink: a(/^!?\[(label)\]\s*\[([^\]]*)\]/).replace("label", D).getRegex()
}, Ue = {
	...Ve,
	emStrongRDelimAst: De,
	emStrongLDelim: we,
	delLDelim: ke,
	delRDelim: Ae,
	url: a(/^emailProtocol|^((?:protocol):\/\/|www\.)(?:[a-zA-Z0-9\-]+\.?)+[^\s<]*|^email/).replace("emailProtocol", Be).replace("protocol", k).replace("email", /[A-Za-z0-9._+-]+(@)[a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]*[a-zA-Z0-9])+(?![\w-])/).getRegex(),
	_backpedal: /(?:[^?!.,:;*_'"~()&]+|\([^)]*\)|&(?![a-zA-Z0-9]+;$)|[?!.,:;*_'"~)]+(?!$))+/,
	del: /^(~~?)(?=[^\s~])((?:\\[\s\S]|[^\\])*?(?:\\[\s\S]|[^\s~\\]))\1(?=[^~]|$)/,
	text: a(/^(?:[^a-zA-Z0-9](?=emailProtocol)|(`+|~+|[^`~])(?:(?=[`~])|(?= {2,}\n)|(?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@)|[\s\S]*?(?:(?=[\\<!\[`*~_]|\b_|protocol:\/\/|www\.|$)|[^ ](?= {2,}\n)|[^a-zA-Z0-9](?=emailProtocol)|[^a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-](?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@))))/).replace("protocol", k).replace(/emailProtocol/g, /(?:mailto|xmpp):/).getRegex()
}, We = {
	...Ue,
	br: a(pe).replace("{2,}", "*").getRegex(),
	text: a(Ue.text).replace("\\b_", "\\b_| {2,}\\n").replace(/\{2,\}/g, "*").getRegex()
}, Ge = {
	normal: se,
	gfm: le,
	pedantic: ue
}, A = {
	normal: Ve,
	gfm: Ue,
	breaks: We,
	pedantic: He
}, Ke = {
	"&": "&amp;",
	"<": "&lt;",
	">": "&gt;",
	"\"": "&quot;",
	"'": "&#39;"
}, j = (e) => Ke[e];
function M(e, t) {
	if (t) {
		if (s.escapeTest.test(e)) return e.replace(s.escapeReplace, j);
	} else if (s.escapeTestNoEncode.test(e)) return e.replace(s.escapeReplaceNoEncode, j);
	return e;
}
function qe(e) {
	return e.replace(s.numericCharacterReference, (e, t, n) => {
		let r = t === void 0 ? Number.parseInt(n, 16) : Number.parseInt(t, 10);
		return r === 0 || r > 1114111 || r >= 55296 && r <= 57343 ? "�" : String.fromCodePoint(r);
	});
}
function Je(e) {
	try {
		e = encodeURI(e).replace(s.percentDecode, "%");
	} catch {
		return null;
	}
	return e;
}
function Ye(e, t) {
	let n = e.replace(s.findPipe, (e, t, n) => {
		let r = !1, i = t;
		for (; --i >= 0 && n[i] === "\\";) r = !r;
		return r ? "|" : " |";
	}).split(s.splitPipe), r = 0;
	if (n[0].trim() || n.shift(), n.length > 0 && !n.at(-1)?.trim() && n.pop(), t) {
		if (n.length > t) n.splice(t);
		else for (; n.length < t;) n.push("");
	}
	for (; r < n.length; r++) n[r] = n[r].trim().replace(s.slashPipe, "|");
	return n;
}
function N(e, t, n) {
	let r = e.length;
	if (r === 0) return "";
	let i = 0;
	for (; i < r;) {
		let a = e.charAt(r - i - 1);
		if (a === t && !n) i++;
		else if (a !== t && n) i++;
		else break;
	}
	return e.slice(0, r - i);
}
function Xe(e) {
	let t = e.split("\n"), n = t.length - 1;
	for (; n >= 0 && s.blankLine.test(t[n]);) n--;
	return t.length - n <= 2 ? e : t.slice(0, n + 1).join("\n");
}
function Ze(e) {
	return e.trim().toLowerCase().toUpperCase().toLowerCase();
}
function P(e, t) {
	if (e.indexOf(t[0]) === -1 && e.indexOf(t[1]) === -1) return -1;
	let n = 0;
	for (let r = 0; r < e.length; r++) if (e[r] === "\\") r++;
	else if (e[r] === t[0]) n++;
	else if (e[r] === t[1] && (n--, n < 0)) return r;
	return n > 0 ? -2 : -1;
}
function Qe(e, t = 0) {
	let n = t, r = "";
	for (let t of e) if (t === "	") {
		let e = 4 - n % 4;
		r += " ".repeat(e), n += e;
	} else r += t, n++;
	return r;
}
function $e(e, t, n, r, i) {
	let a = t.href, o = t.title || null, s = e[1].replace(i.other.outputLinkReplace, "$1"), c = e[0].charAt(0) === "!";
	r.state.inLink = !0;
	let l = r.state.linkEmitted, u = r.state.inRawBlock;
	r.state.linkEmitted = !1;
	let d = r.inlineTokens(s), f = r.state.linkEmitted;
	if (r.state.linkEmitted = l, r.state.inLink = !1, !c) {
		if (f) {
			r.state.inRawBlock = u;
			return;
		}
		r.state.linkEmitted = !0;
	}
	return {
		type: c ? "image" : "link",
		raw: n,
		href: a,
		title: o,
		text: s,
		tokens: d
	};
}
function et(e, t, n) {
	let r = e.match(n.other.indentCodeCompensation);
	if (r === null) return t;
	let i = r[1];
	return t.split("\n").map((e) => {
		let t = e.match(n.other.beginningSpace);
		if (t === null) return e;
		let [r] = t;
		return e.slice(Math.min(r.length, i.length));
	}).join("\n");
}
function tt(e, t, n, r) {
	if (!t.includes("<")) return !1;
	for (let i = 0; i < t.length; i++) {
		if (t[i] === "\\") {
			i++;
			continue;
		}
		if (t[i] === "`") {
			let e = r.inline.code.exec(t.slice(i));
			if (e) {
				i += e[0].length - 1;
				continue;
			}
		}
		if (t[i] !== "<") continue;
		let a = e.slice(n + i), o = r.inline.tag.exec(a) || r.inline.autolink.exec(a);
		if (o) {
			if (o[0].length > t.length - i) return !0;
			i += o[0].length - 1;
		}
	}
	return !1;
}
var nt = class {
	options;
	rules;
	lexer;
	constructor(e) {
		this.options = e || t;
	}
	space(e) {
		let t = this.rules.block.newline.exec(e);
		if (t && t[0].length > 0) return {
			type: "space",
			raw: t[0]
		};
	}
	code(e) {
		let t = this.rules.block.code.exec(e);
		if (t) {
			let e = this.options.pedantic ? t[0] : Xe(t[0]);
			return {
				type: "code",
				raw: e,
				codeBlockStyle: "indented",
				text: e.replace(this.rules.other.codeRemoveIndent, "")
			};
		}
	}
	fences(e) {
		let t = this.rules.block.fences.exec(e);
		if (t) {
			let e = t[0], n = et(e, t[3] || "", this.rules);
			return {
				type: "code",
				raw: e,
				lang: t[2] ? t[2].trim().replace(this.rules.inline.anyPunctuation, "$1") : t[2],
				text: n
			};
		}
	}
	heading(e) {
		let t = this.rules.block.heading.exec(e);
		if (t) {
			let e = t[2].trim();
			if (this.rules.other.endingHash.test(e)) {
				let t = N(e, "#");
				(this.options.pedantic || !t || this.rules.other.endingSpaceTabChar.test(t)) && (e = t.trim());
			}
			return {
				type: "heading",
				raw: N(t[0], "\n"),
				depth: t[1].length,
				text: e,
				tokens: this.lexer.inline(e)
			};
		}
	}
	hr(e) {
		let t = this.rules.block.hr.exec(e);
		if (t) return {
			type: "hr",
			raw: N(t[0], "\n")
		};
	}
	blockquote(e) {
		let t = this.rules.block.blockquote.exec(e);
		if (t) {
			let e = N(t[0], "\n").split("\n"), n = "", r = "", i = [];
			for (; e.length > 0;) {
				let t = !1, a = [], o;
				for (o = 0; o < e.length; o++) if (this.rules.other.blockquoteStart.test(e[o])) a.push(e[o]), t = !0;
				else if (!t) a.push(e[o]);
				else break;
				e = e.slice(o);
				let s = a.join("\n"), c = s.replace(this.rules.other.blockquoteSetextReplace, "\n    $1").replace(this.rules.other.blockquoteSetextReplace2, "");
				n = n ? `${n}
${s}` : s, r = r ? `${r}
${c}` : c;
				let l = this.lexer.state.top;
				if (this.lexer.state.top = !0, this.lexer.blockTokens(c, i, !0), this.lexer.state.top = l, e.length === 0) break;
				let u = i.at(-1);
				if (u?.type === "code") break;
				if (u?.type === "blockquote") {
					let t = u, a = e.join("\n"), o = t.raw + "\n" + a.replace(this.rules.other.blockquoteSetextReplace2, ""), s = this.blockquote(o);
					i[i.length - 1] = s;
					let c = o.substring(s.raw.length).replace(/^\n/, ""), l = c ? c.split("\n").length : 0, d = l ? e.slice(0, -l) : e;
					d.length > 0 && (n = `${n}
${d.join("\n")}`), r = r.substring(0, r.length - t.text.length) + s.text;
					break;
				}
				if (u?.type === "list") {
					let t = u, a = t.raw + "\n" + e.join("\n"), o = this.list(a);
					i[i.length - 1] = o, n = n.substring(0, n.length - u.raw.length) + o.raw, r = r.substring(0, r.length - t.raw.length) + o.raw, e = a.substring(i.at(-1).raw.length).split("\n");
					continue;
				}
			}
			return {
				type: "blockquote",
				raw: n,
				tokens: i,
				text: r
			};
		}
	}
	list(e) {
		let t = this.rules.block.list.exec(e);
		if (t) {
			let n = t[1].trim(), r = n.length > 1, i = {
				type: "list",
				raw: "",
				ordered: r,
				start: r ? +n.slice(0, -1) : "",
				loose: !1,
				items: []
			};
			n = r ? `\\d{1,9}\\${n.slice(-1)}` : `\\${n}`, this.options.pedantic && (n = r ? n : "[*+-]");
			let a = this.rules.other.listItemRegex(n), o = !1;
			for (; e;) {
				let n = !1, r = "", s = "";
				if (!(t = a.exec(e)) || this.rules.block.hr.test(e)) break;
				r = t[0], e = e.substring(r.length);
				let c = t[2].split("\n", 1)[0], l = t[1].length, u = this.options.pedantic ? Qe(c, l) : c.replace(this.rules.other.leadingSpaceTab, (e) => Qe(e, l)), d = e.split("\n", 1)[0], f = !u.trim(), p = 0;
				if (this.options.pedantic ? (p = 2, s = u.trimStart()) : f ? p = l + 1 : (p = u.search(this.rules.other.nonSpaceChar), p = p > 4 ? 1 : p, s = u.slice(p), p += l), f && this.rules.other.blankLine.test(d) && (r += d + "\n", e = e.substring(d.length + 1), n = !0), !n) {
					let t = this.rules.other.nextBulletRegex(p), n = this.rules.other.hrRegex(p), i = this.rules.other.fencesBeginRegex(p), a = this.rules.other.headingBeginRegex(p), o = this.rules.other.htmlBeginRegex(p), c = this.rules.other.blockquoteBeginRegex(p);
					for (; e;) {
						let l = e.split("\n", 1)[0], m;
						if (d = l, this.options.pedantic ? (d = d.replace(this.rules.other.listReplaceNesting, "  "), m = d) : m = d.replace(this.rules.other.leadingSpaceTab, (e) => e.replace(this.rules.other.tabCharGlobal, "    ")), i.test(d) || a.test(d) || o.test(d) || c.test(d) || t.test(d) || n.test(d)) break;
						if (m.search(this.rules.other.nonSpaceChar) >= p || !d.trim()) s += "\n" + m.slice(p);
						else {
							if (f || u.replace(this.rules.other.tabCharGlobal, "    ").search(this.rules.other.nonSpaceChar) >= 4 || i.test(u) || a.test(u) || n.test(u)) break;
							s += "\n" + d;
						}
						f = !d.trim(), r += l + "\n", e = e.substring(l.length + 1), u = m.slice(p);
					}
				}
				i.loose || (o ? i.loose = !0 : this.rules.other.doubleBlankLine.test(r) && (o = !0)), i.items.push({
					type: "list_item",
					raw: r,
					task: !!this.options.gfm && this.rules.other.listIsTask.test(s),
					loose: !1,
					text: s,
					tokens: []
				}), i.raw += r;
			}
			let s = i.items.at(-1);
			if (s) s.raw = s.raw.trimEnd(), s.text = s.text.trimEnd();
			else return;
			i.raw = i.raw.trimEnd();
			for (let e of i.items) if (this.lexer.state.top = !1, e.tokens = this.lexer.blockTokens(e.text, []), !i.loose) {
				let t = e.tokens.filter((e) => e.type === "space");
				i.loose = t.length > 0 && t.some((e) => this.rules.other.anyLine.test(e.raw));
			}
			for (let e of i.items) {
				let t = e.tokens[0];
				if (e.task && (t?.type === "text" || t?.type === "paragraph")) {
					e.text = e.text.replace(this.rules.other.listReplaceTask, ""), t.raw = t.raw.replace(this.rules.other.listReplaceTask, ""), t.text = t.text.replace(this.rules.other.listReplaceTask, "");
					for (let e = this.lexer.inlineQueue.length - 1; e >= 0; e--) if (this.rules.other.listIsTask.test(this.lexer.inlineQueue[e].src)) {
						this.lexer.inlineQueue[e].src = this.lexer.inlineQueue[e].src.replace(this.rules.other.listReplaceTask, "");
						break;
					}
					let n = this.rules.other.listTaskCheckbox.exec(e.raw);
					if (n) {
						let t = {
							type: "checkbox",
							raw: n[0] + " ",
							checked: n[0] !== "[ ]"
						};
						e.checked = t.checked, i.loose ? e.tokens[0] && ["paragraph", "text"].includes(e.tokens[0].type) && "tokens" in e.tokens[0] && e.tokens[0].tokens ? (e.tokens[0].raw = t.raw + e.tokens[0].raw, e.tokens[0].text = t.raw + e.tokens[0].text, e.tokens[0].tokens.unshift(t)) : e.tokens.unshift({
							type: "paragraph",
							raw: t.raw,
							text: t.raw,
							tokens: [t]
						}) : e.tokens.unshift(t);
					}
				} else e.task &&= !1;
			}
			if (i.loose) for (let e of i.items) {
				e.loose = !0;
				for (let t of e.tokens) t.type === "text" && (t.type = "paragraph");
			}
			return i;
		}
	}
	html(e) {
		let t = this.rules.block.html.exec(e);
		if (t) {
			let e = Xe(t[0]);
			return {
				type: "html",
				block: !0,
				raw: e,
				pre: t[1] === "pre" || t[1] === "script" || t[1] === "style",
				text: e
			};
		}
	}
	def(e) {
		let t = this.rules.block.def.exec(e);
		if (t) {
			if (!this.rules.other.startAngleBracket.test(t[2]) && P(t[2], "()") !== -1) return;
			let e = Ze(t[1]).replace(this.rules.other.multipleSpaceGlobal, " "), n = t[2] ? t[2].replace(this.rules.other.hrefBrackets, "$1").replace(this.rules.inline.anyPunctuation, "$1") : "", r = t[3] ? t[3].substring(1, t[3].length - 1).replace(this.rules.inline.anyPunctuation, "$1") : t[3];
			return {
				type: "def",
				tag: e,
				raw: N(t[0], "\n"),
				href: n,
				title: r
			};
		}
	}
	table(e) {
		let t = this.rules.block.table.exec(e);
		if (!t || !this.rules.other.tableDelimiter.test(t[2])) return;
		let n = Ye(t[1]), r = t[2].replace(this.rules.other.tableAlignChars, "").split("|"), i = t[3]?.trim() ? t[3].replace(this.rules.other.tableRowBlankLine, "").split("\n") : [], a = {
			type: "table",
			raw: N(t[0], "\n"),
			header: [],
			align: [],
			rows: []
		};
		if (n.length === r.length) {
			for (let e of r) this.rules.other.tableAlignRight.test(e) ? a.align.push("right") : this.rules.other.tableAlignCenter.test(e) ? a.align.push("center") : this.rules.other.tableAlignLeft.test(e) ? a.align.push("left") : a.align.push(null);
			for (let e = 0; e < n.length; e++) a.header.push({
				text: n[e],
				tokens: this.lexer.inline(n[e]),
				header: !0,
				align: a.align[e]
			});
			for (let e of i) a.rows.push(Ye(e, a.header.length).map((e, t) => ({
				text: e,
				tokens: this.lexer.inline(e),
				header: !1,
				align: a.align[t]
			})));
			return a;
		}
	}
	lheading(e) {
		let t = this.rules.block.lheading.exec(e);
		if (t) {
			let e = t[1].trim();
			return {
				type: "heading",
				raw: N(t[0], "\n"),
				depth: t[2].charAt(0) === "=" ? 1 : 2,
				text: e,
				tokens: this.lexer.inline(e)
			};
		}
	}
	paragraph(e) {
		let t = this.rules.block.paragraph.exec(e);
		if (t) {
			let e = t[1].charAt(t[1].length - 1) === "\n" ? t[1].slice(0, -1) : t[1];
			return {
				type: "paragraph",
				raw: t[0],
				text: e,
				tokens: this.lexer.inline(e)
			};
		}
	}
	text(e) {
		let t = this.rules.block.text.exec(e);
		if (t) return {
			type: "text",
			raw: t[0],
			text: t[0],
			tokens: this.lexer.inline(t[0])
		};
	}
	escape(e) {
		let t = this.rules.inline.escape.exec(e);
		if (t) return {
			type: "escape",
			raw: t[0],
			text: t[1]
		};
	}
	tag(e) {
		let t = this.rules.inline.tag.exec(e);
		if (t) return !this.lexer.state.inLink && this.rules.other.startATag.test(t[0]) ? this.lexer.state.inLink = !0 : this.lexer.state.inLink && this.rules.other.endATag.test(t[0]) && (this.lexer.state.inLink = !1), !this.lexer.state.inRawBlock && this.rules.other.startPreScriptTag.test(t[0]) ? this.lexer.state.inRawBlock = !0 : this.lexer.state.inRawBlock && this.rules.other.endPreScriptTag.test(t[0]) && (this.lexer.state.inRawBlock = !1), {
			type: "html",
			raw: t[0],
			inLink: this.lexer.state.inLink,
			inRawBlock: this.lexer.state.inRawBlock,
			block: !1,
			text: t[0]
		};
	}
	link(e) {
		if (this.lexer.state.linkParenPossible === !1) return;
		let t = this.rules.inline.link.exec(e);
		if (t) {
			let n = t[0].charAt(0) === "!" ? 2 : 1;
			if (!this.options.pedantic && tt(e, t[1], n, this.rules)) return;
			let r = t[2].trim();
			if (!this.options.pedantic && this.rules.other.startAngleBracket.test(r)) {
				if (!this.rules.other.endAngleBracket.test(r)) return;
				let e = N(r.slice(0, -1), "\\");
				if ((r.length - e.length) % 2 == 0) return;
			} else {
				let e = P(t[2], "()");
				if (e === -2) return;
				if (e > -1) {
					let n = (t[0].indexOf("!") === 0 ? 5 : 4) + t[1].length + e;
					t[2] = t[2].substring(0, e), t[0] = t[0].substring(0, n).trim(), t[3] = "";
				}
			}
			let i = t[2], a = "";
			if (this.options.pedantic) {
				let e = this.rules.other.pedanticHrefTitle.exec(i);
				e && (i = e[1], a = e[3]);
			} else a = t[3] ? t[3].slice(1, -1) : "";
			return i = i.trim(), this.rules.other.startAngleBracket.test(i) && (i = this.options.pedantic && !this.rules.other.endAngleBracket.test(r) ? i.slice(1) : i.slice(1, -1)), $e(t, {
				href: i && i.replace(this.rules.inline.anyPunctuation, "$1"),
				title: a && a.replace(this.rules.inline.anyPunctuation, "$1")
			}, t[0], this.lexer, this.rules);
		}
	}
	reflink(e, t) {
		let n;
		if ((n = this.rules.inline.reflink.exec(e)) || (n = this.rules.inline.nolink.exec(e))) {
			let r = n[0].charAt(0) === "!" ? 2 : 1;
			if (!this.options.pedantic && tt(e, n[1], r, this.rules)) return;
			let i = t[Ze((n[2] || n[1]).replace(this.rules.other.multipleSpaceGlobal, " "))];
			if (!i) {
				let e = n[0].charAt(0);
				return {
					type: "text",
					raw: e,
					text: e
				};
			}
			return $e(n, i, n[0], this.lexer, this.rules);
		}
	}
	emStrong(e, t, n = "") {
		let r = this.rules.inline.emStrongLDelim.exec(e);
		if (!(!r || !r[1] && !r[2] && !r[3] && !r[4] || r[4] && n.match(this.rules.other.unicodeAlphaNumeric)) && (!(r[1] || r[3]) || !n || this.rules.inline.punctuation.exec(n))) {
			let i = [...r[0]].length - 1, a, o, s = i, c = 0, l = r[0][0], u = n === l, d = l === "*" ? this.rules.inline.emStrongRDelimAst : this.rules.inline.emStrongRDelimUnd;
			for (d.lastIndex = 0, t = t.slice(-1 * e.length + i); (r = d.exec(t)) !== null;) {
				if (a = r[1] || r[2] || r[3] || r[4] || r[5] || r[6], !a) continue;
				if (o = [...a].length, r[3] || r[4]) {
					s += o;
					continue;
				}
				if (r[5] || r[6]) {
					if (i % 3 && !((i + o) % 3)) {
						c += o;
						continue;
					}
					if (u) break;
				}
				if (s -= o, s > 0) continue;
				o = Math.min(o, o + s + c);
				let t = [...r[0]][0].length, n = e.slice(0, i + r.index + t + o);
				if (Math.min(i, o) % 2) {
					let e = n.slice(1, -1);
					return {
						type: "em",
						raw: n,
						text: e,
						tokens: this.lexer.inlineTokens(e)
					};
				}
				let l = n.slice(2, -2);
				return {
					type: "strong",
					raw: n,
					text: l,
					tokens: this.lexer.inlineTokens(l)
				};
			}
		}
	}
	codespan(e) {
		let t = this.rules.inline.code.exec(e);
		if (t) {
			let e = t[2].replace(this.rules.other.newLineCharGlobal, " "), n = this.rules.other.nonSpaceChar.test(e), r = this.rules.other.startingSpaceChar.test(e) && this.rules.other.endingSpaceChar.test(e);
			return n && r && (e = e.substring(1, e.length - 1)), {
				type: "codespan",
				raw: t[0],
				text: e
			};
		}
	}
	br(e) {
		let t = this.rules.inline.br.exec(e);
		if (t) return {
			type: "br",
			raw: t[0]
		};
	}
	del(e, t, n = "") {
		let r = this.rules.inline.delLDelim.exec(e);
		if (r && (!r[1] || !n || this.rules.inline.punctuation.exec(n))) {
			let n = [...r[0]].length - 1, i, a, o = n, s = this.rules.inline.delRDelim;
			for (s.lastIndex = 0, t = t.slice(-1 * e.length + n); (r = s.exec(t)) !== null;) {
				if (i = r[1] || r[2] || r[3] || r[4] || r[5] || r[6], !i || (a = [...i].length, a !== n)) continue;
				if (r[3] || r[4]) {
					o += a;
					continue;
				}
				if (o -= a, o > 0) continue;
				a = Math.min(a, a + o);
				let t = [...r[0]][0].length, s = e.slice(0, n + r.index + t + a), c = s.slice(n, -n);
				return {
					type: "del",
					raw: s,
					text: c,
					tokens: this.lexer.inlineTokens(c)
				};
			}
		}
	}
	autolink(e) {
		let t = this.rules.inline.autolink.exec(e);
		if (t) {
			let e, n;
			return t[2] === "@" ? (e = t[1], n = "mailto:" + e) : (e = t[1], n = e), {
				type: "link",
				raw: t[0],
				text: e,
				href: n,
				autolink: !0,
				tokens: [{
					type: "text",
					raw: e,
					text: e
				}]
			};
		}
	}
	url(e) {
		let t;
		if (t = this.rules.inline.url.exec(e)) {
			let e, n;
			if (t[2] === "@") e = t[0], n = "mailto:" + e;
			else {
				let r;
				do
					r = t[0], t[0] = this.rules.inline._backpedal.exec(t[0])?.[0] ?? "";
				while (r !== t[0]);
				e = t[0], n = t[1] === "www." ? "http://" + t[0] : t[0];
			}
			return {
				type: "link",
				raw: t[0],
				text: e,
				href: n,
				autolink: !0,
				tokens: [{
					type: "text",
					raw: e,
					text: e
				}]
			};
		}
	}
	inlineText(e) {
		let t = this.rules.inline.text.exec(e);
		if (t) {
			let e = this.lexer.state.inRawBlock;
			return {
				type: "text",
				raw: t[0],
				text: e ? t[0] : qe(t[0]),
				escaped: e
			};
		}
	}
}, F = class e {
	tokens;
	options;
	state;
	inlineQueue;
	tokenizer;
	constructor(e) {
		this.tokens = [], this.tokens.links = Object.create(null), this.options = e || t, this.options.tokenizer = this.options.tokenizer || new nt(), this.tokenizer = this.options.tokenizer, this.tokenizer.options = this.options, this.tokenizer.lexer = this, this.inlineQueue = [], this.state = {
			inLink: !1,
			inRawBlock: !1,
			linkEmitted: !1,
			linkParenPossible: !0,
			top: !0
		};
		let n = {
			other: s,
			block: Ge.normal,
			inline: A.normal
		};
		this.options.pedantic ? (n.block = Ge.pedantic, n.inline = A.pedantic) : this.options.gfm && (n.block = Ge.gfm, n.inline = this.options.breaks ? A.breaks : A.gfm), this.tokenizer.rules = n;
	}
	static get rules() {
		return {
			block: Ge,
			inline: A
		};
	}
	static lex(t, n) {
		return new e(n).lex(t);
	}
	static lexInline(t, n) {
		return new e(n).inlineTokens(t);
	}
	lex(e) {
		e = e.replace(s.carriageReturn, "\n"), this.blockTokens(e, this.tokens);
		for (let e = 0; e < this.inlineQueue.length; e++) {
			let t = this.inlineQueue[e];
			this.inlineTokens(t.src, t.tokens);
		}
		return this.inlineQueue = [], this.tokens;
	}
	blockTokens(e, t = [], n = !1) {
		this.tokenizer.lexer = this, this.options.pedantic && (e = e.replace(s.tabCharGlobal, "    ").replace(s.spaceLine, ""));
		let r = 1 / 0;
		for (; e;) {
			if (e.length < r) r = e.length;
			else {
				this.infiniteLoopError(e.charCodeAt(0));
				break;
			}
			let i;
			if (this.options.extensions?.block?.some((n) => (i = n.call({ lexer: this }, e, t)) ? (e = e.substring(i.raw.length), t.push(i), !0) : !1)) continue;
			if (i = this.tokenizer.space(e)) {
				e = e.substring(i.raw.length);
				let n = t.at(-1);
				i.raw.length === 1 && n !== void 0 ? n.raw += "\n" : t.push(i);
				continue;
			}
			if (i = this.tokenizer.code(e)) {
				e = e.substring(i.raw.length);
				let n = t.at(-1);
				n?.type === "paragraph" || n?.type === "text" ? (n.raw += (n.raw.endsWith("\n") ? "" : "\n") + i.raw, n.text += "\n" + i.text, this.inlineQueue.at(-1).src = n.text) : t.push(i);
				continue;
			}
			if (i = this.tokenizer.fences(e)) {
				e = e.substring(i.raw.length), t.push(i);
				continue;
			}
			if (i = this.tokenizer.heading(e)) {
				e = e.substring(i.raw.length), t.push(i);
				continue;
			}
			if (i = this.tokenizer.hr(e)) {
				e = e.substring(i.raw.length), t.push(i);
				continue;
			}
			if (i = this.tokenizer.blockquote(e)) {
				e = e.substring(i.raw.length), t.push(i);
				continue;
			}
			if (i = this.tokenizer.list(e)) {
				e = e.substring(i.raw.length), t.push(i);
				continue;
			}
			if (i = this.tokenizer.html(e)) {
				e = e.substring(i.raw.length), t.push(i);
				continue;
			}
			if (i = this.tokenizer.def(e)) {
				e = e.substring(i.raw.length);
				let n = t.at(-1);
				n?.type === "paragraph" || n?.type === "text" ? (n.raw += (n.raw.endsWith("\n") ? "" : "\n") + i.raw, n.text += "\n" + i.raw, this.inlineQueue.at(-1).src = n.text) : this.tokens.links[i.tag] || (this.tokens.links[i.tag] = {
					href: i.href,
					title: i.title
				}, t.push(i));
				continue;
			}
			if (i = this.tokenizer.table(e)) {
				e = e.substring(i.raw.length), t.push(i);
				continue;
			}
			if (i = this.tokenizer.lheading(e)) {
				e = e.substring(i.raw.length), t.push(i);
				continue;
			}
			let a = e;
			if (this.options.extensions?.startBlock) {
				let t = 1 / 0, n = e.slice(1), r;
				this.options.extensions.startBlock.forEach((e) => {
					r = e.call({ lexer: this }, n), typeof r == "number" && r >= 0 && (t = Math.min(t, r));
				}), t < 1 / 0 && t >= 0 && (a = e.substring(0, t + 1));
			}
			if (this.state.top && (i = this.tokenizer.paragraph(a))) {
				let r = t.at(-1);
				n && r?.type === "paragraph" ? (r.raw += (r.raw.endsWith("\n") ? "" : "\n") + i.raw, r.text += "\n" + i.text, this.inlineQueue.pop(), this.inlineQueue.at(-1).src = r.text) : t.push(i), n = a.length !== e.length, e = e.substring(i.raw.length);
				continue;
			}
			if (i = this.tokenizer.text(e)) {
				e = e.substring(i.raw.length);
				let n = t.at(-1);
				n?.type === "text" ? (n.raw += (n.raw.endsWith("\n") ? "" : "\n") + i.raw, n.text += "\n" + i.text, this.inlineQueue.pop(), this.inlineQueue.at(-1).src = n.text) : t.push(i);
				continue;
			}
			if (e) {
				this.infiniteLoopError(e.charCodeAt(0));
				break;
			}
		}
		return this.state.top = !0, t;
	}
	inline(e, t = []) {
		return this.inlineQueue.push({
			src: e,
			tokens: t
		}), t;
	}
	linkInText(e) {
		if (!e.includes("[")) return !1;
		let t = this.tokenizer.rules.inline.link;
		for (let n of e.matchAll(this.tokenizer.rules.inline.blockSkip)) if (t.test(n[0]) && e.charAt(n.index - 1) !== "!") return !0;
		for (let t of e.matchAll(this.tokenizer.rules.inline.reflinkSearch)) {
			let e = t[0], n = e.lastIndexOf("[");
			if (!(e.charAt(0) === "!" || !Object.hasOwn(this.tokens.links, Ze(e.slice(n + 1, -1)))) && !(n > 1 && this.linkInText(e.slice(1, n - 1)))) return !0;
		}
		return !1;
	}
	inlineTokens(e, t = []) {
		this.tokenizer.lexer = this;
		let n = this.state.linkParenPossible;
		this.state.linkParenPossible = n && e.includes(")");
		try {
			return this.#e(e, t);
		} finally {
			this.state.linkParenPossible = n;
		}
	}
	#e(e, t) {
		let n = e;
		if (this.tokens.links && e.includes("[")) {
			let e = this.tokenizer.rules.inline.reflinkSearch, t = (n) => {
				let r = n.lastIndexOf("[");
				if (!Object.hasOwn(this.tokens.links, Ze(n.slice(r + 1, -1)))) return n;
				if (r > 1 && n.charAt(0) !== "!") {
					let i = n.slice(1, r - 1);
					if (this.linkInText(i)) return "[" + i.replace(e, t) + "][" + "a".repeat(n.length - r - 2) + "]";
				}
				return "[" + "a".repeat(n.length - 2) + "]";
			};
			n = n.replace(e, t);
		}
		n = n.replace(this.tokenizer.rules.inline.anyPunctuation, (e) => "+".repeat(e.length)), n = n.replace(this.tokenizer.rules.inline.blockSkip, (e, t, n) => {
			let r = n ? n.length : 0;
			return e.slice(0, r) + "[" + "a".repeat(e.length - r - 2) + "]";
		}), n = this.options.hooks?.emStrongMask?.call({ lexer: this }, n) ?? n;
		let r = !1, i = "", a = 1 / 0;
		for (; e;) {
			if (e.length < a) a = e.length;
			else {
				this.infiniteLoopError(e.charCodeAt(0));
				break;
			}
			r || (i = ""), r = !1;
			let o;
			if (this.options.extensions?.inline?.some((n) => (o = n.call({ lexer: this }, e, t)) ? (e = e.substring(o.raw.length), t.push(o), !0) : !1)) continue;
			if (o = this.tokenizer.escape(e)) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			if (o = this.tokenizer.tag(e)) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			if (o = this.tokenizer.link(e)) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			if (o = this.tokenizer.reflink(e, this.tokens.links)) {
				e = e.substring(o.raw.length);
				let n = t.at(-1);
				o.type === "text" && n?.type === "text" ? (n.raw += o.raw, n.text += o.text) : t.push(o);
				continue;
			}
			if (o = this.tokenizer.emStrong(e, n, i)) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			if (o = this.tokenizer.codespan(e)) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			if (o = this.tokenizer.br(e)) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			if (o = this.tokenizer.del(e, n, i)) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			if (o = this.tokenizer.autolink(e)) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			if (!this.state.inLink && (o = this.tokenizer.url(e))) {
				e = e.substring(o.raw.length), t.push(o);
				continue;
			}
			let s = e;
			if (this.options.extensions?.startInline) {
				let t = 1 / 0, n = e.slice(1), r;
				this.options.extensions.startInline.forEach((e) => {
					r = e.call({ lexer: this }, n), typeof r == "number" && r >= 0 && (t = Math.min(t, r));
				}), t < 1 / 0 && t >= 0 && (s = e.substring(0, t + 1));
			}
			if (o = this.tokenizer.inlineText(s)) {
				e = e.substring(o.raw.length), o.raw.slice(-1) !== "_" && (i = o.raw.slice(-1)), r = !0;
				let n = t.at(-1);
				n?.type === "text" ? (n.raw += o.raw, n.text += o.text) : t.push(o);
				continue;
			}
			if (e) {
				this.infiniteLoopError(e.charCodeAt(0));
				break;
			}
		}
		return t;
	}
	infiniteLoopError(e) {
		let t = "Infinite loop on byte: " + e;
		if (this.options.silent) console.error(t);
		else throw Error(t);
	}
}, rt = class {
	options;
	parser;
	constructor(e) {
		this.options = e || t;
	}
	space(e) {
		return "";
	}
	code({ text: e, lang: t, escaped: n }) {
		let r = (t || "").match(s.notSpaceStart)?.[0], i = e ? e.replace(s.endingNewline, "") + "\n" : "";
		return r ? "<pre><code class=\"language-" + M(r) + "\">" + (n ? i : M(i, !0)) + "</code></pre>\n" : "<pre><code>" + (n ? i : M(i, !0)) + "</code></pre>\n";
	}
	blockquote({ tokens: e }) {
		return `<blockquote>
${this.parser.parse(e)}</blockquote>
`;
	}
	html({ text: e }) {
		return e;
	}
	def(e) {
		return "";
	}
	heading({ tokens: e, depth: t }) {
		return `<h${t}>${this.parser.parseInline(e)}</h${t}>
`;
	}
	hr(e) {
		return "<hr>\n";
	}
	list(e) {
		let t = e.ordered, n = e.start, r = "";
		for (let t = 0; t < e.items.length; t++) {
			let n = e.items[t];
			r += this.listitem(n);
		}
		let i = t ? "ol" : "ul", a = t && n !== 1 ? " start=\"" + n + "\"" : "";
		return "<" + i + a + ">\n" + r + "</" + i + ">\n";
	}
	listitem(e) {
		return `<li>${this.parser.parse(e.tokens)}</li>
`;
	}
	checkbox({ checked: e }) {
		return "<input " + (e ? "checked=\"\" " : "") + "disabled=\"\" type=\"checkbox\"> ";
	}
	paragraph({ tokens: e }) {
		return `<p>${this.parser.parseInline(e)}</p>
`;
	}
	table(e) {
		let t = "", n = "";
		for (let t = 0; t < e.header.length; t++) n += this.tablecell(e.header[t]);
		t += this.tablerow({ text: n });
		let r = "";
		for (let t = 0; t < e.rows.length; t++) {
			let i = e.rows[t];
			n = "";
			for (let e = 0; e < i.length; e++) n += this.tablecell(i[e]);
			r += this.tablerow({ text: n });
		}
		return r &&= `<tbody>${r}</tbody>`, "<table>\n<thead>\n" + t + "</thead>\n" + r + "</table>\n";
	}
	tablerow({ text: e }) {
		return `<tr>
${e}</tr>
`;
	}
	tablecell(e) {
		let t = this.parser.parseInline(e.tokens), n = e.header ? "th" : "td";
		return (e.align ? `<${n} align="${e.align}">` : `<${n}>`) + t + `</${n}>
`;
	}
	strong({ tokens: e }) {
		return `<strong>${this.parser.parseInline(e)}</strong>`;
	}
	em({ tokens: e }) {
		return `<em>${this.parser.parseInline(e)}</em>`;
	}
	codespan({ text: e }) {
		return `<code>${M(e, !0)}</code>`;
	}
	br(e) {
		return "<br>";
	}
	del({ tokens: e }) {
		return `<del>${this.parser.parseInline(e)}</del>`;
	}
	link({ href: e, title: t, text: n, tokens: r, autolink: i }) {
		let a = i ? M(n, !0) : this.parser.parseInline(r), o = Je(e);
		if (o === null) return a;
		e = M(o, i);
		let s = "<a href=\"" + e + "\"";
		return t && (s += " title=\"" + M(t) + "\""), s += ">" + a + "</a>", s;
	}
	image({ href: e, title: t, text: n, tokens: r }) {
		r && (n = this.parser.parseInline(r, this.parser.textRenderer));
		let i = Je(e);
		if (i === null) return M(n);
		e = i;
		let a = `<img src="${M(e)}" alt="${M(n)}"`;
		return t && (a += ` title="${M(t)}"`), a += ">", a;
	}
	text(e) {
		return "tokens" in e && e.tokens ? this.parser.parseInline(e.tokens) : "escaped" in e && e.escaped ? e.text : M(e.text);
	}
}, it = class {
	strong({ text: e }) {
		return e;
	}
	em({ text: e }) {
		return e;
	}
	codespan({ text: e }) {
		return e;
	}
	del({ text: e }) {
		return e;
	}
	html({ text: e }) {
		return e;
	}
	text({ text: e }) {
		return e;
	}
	link({ text: e }) {
		return "" + e;
	}
	image({ text: e }) {
		return "" + e;
	}
	br() {
		return "";
	}
	checkbox({ raw: e }) {
		return e;
	}
}, I = class e {
	options;
	renderer;
	textRenderer;
	constructor(e) {
		this.options = e || t, this.options.renderer = this.options.renderer || new rt(), this.renderer = this.options.renderer, this.renderer.options = this.options, this.renderer.parser = this, this.textRenderer = new it();
	}
	static parse(t, n) {
		return new e(n).parse(t);
	}
	static parseInline(t, n) {
		return new e(n).parseInline(t);
	}
	parse(e) {
		this.renderer.parser = this;
		let t = "";
		for (let n = 0; n < e.length; n++) {
			let r = e[n];
			if (this.options.extensions?.renderers?.[r.type]) {
				let e = r, n = this.options.extensions.renderers[e.type].call({ parser: this }, e);
				if (n !== !1 || ![
					"space",
					"hr",
					"heading",
					"code",
					"table",
					"blockquote",
					"list",
					"checkbox",
					"html",
					"def",
					"paragraph",
					"text"
				].includes(e.type)) {
					t += n || "";
					continue;
				}
			}
			let i = r;
			switch (i.type) {
				case "space":
					t += this.renderer.space(i);
					break;
				case "hr":
					t += this.renderer.hr(i);
					break;
				case "heading":
					t += this.renderer.heading(i);
					break;
				case "code":
					t += this.renderer.code(i);
					break;
				case "table":
					t += this.renderer.table(i);
					break;
				case "blockquote":
					t += this.renderer.blockquote(i);
					break;
				case "list":
					t += this.renderer.list(i);
					break;
				case "checkbox":
					t += this.renderer.checkbox(i);
					break;
				case "html":
					t += this.renderer.html(i);
					break;
				case "def":
					t += this.renderer.def(i);
					break;
				case "paragraph":
					t += this.renderer.paragraph(i);
					break;
				case "text":
					t += this.renderer.text(i);
					break;
				default: {
					let e = "Token with \"" + i.type + "\" type was not found.";
					if (this.options.silent) return console.error(e), "";
					throw Error(e);
				}
			}
		}
		return t;
	}
	parseInline(e, t = this.renderer) {
		this.renderer.parser = this;
		let n = "";
		for (let r = 0; r < e.length; r++) {
			let i = e[r];
			if (this.options.extensions?.renderers?.[i.type]) {
				let e = this.options.extensions.renderers[i.type].call({ parser: this }, i);
				if (e !== !1 || ![
					"escape",
					"html",
					"link",
					"image",
					"checkbox",
					"strong",
					"em",
					"codespan",
					"br",
					"del",
					"text"
				].includes(i.type)) {
					n += e || "";
					continue;
				}
			}
			let a = i;
			switch (a.type) {
				case "escape":
					n += t.text(a);
					break;
				case "html":
					n += t.html(a);
					break;
				case "link":
					n += t.link(a);
					break;
				case "image":
					n += t.image(a);
					break;
				case "checkbox":
					n += t.checkbox(a);
					break;
				case "strong":
					n += t.strong(a);
					break;
				case "em":
					n += t.em(a);
					break;
				case "codespan":
					n += t.codespan(a);
					break;
				case "br":
					n += t.br(a);
					break;
				case "del":
					n += t.del(a);
					break;
				case "text":
					n += t.text(a);
					break;
				default: {
					let e = "Token with \"" + a.type + "\" type was not found.";
					if (this.options.silent) return console.error(e), "";
					throw Error(e);
				}
			}
		}
		return n;
	}
}, L = class {
	options;
	block;
	constructor(e) {
		this.options = e || t;
	}
	static passThroughHooks = /* @__PURE__ */ new Set([
		"preprocess",
		"postprocess",
		"processAllTokens",
		"emStrongMask"
	]);
	static passThroughHooksRespectAsync = /* @__PURE__ */ new Set([
		"preprocess",
		"postprocess",
		"processAllTokens"
	]);
	preprocess(e) {
		return e;
	}
	postprocess(e) {
		return e;
	}
	processAllTokens(e) {
		return e;
	}
	emStrongMask(e) {
		return e;
	}
	provideLexer(e = this.block) {
		return e ? F.lex : F.lexInline;
	}
	provideParser(e = this.block) {
		return e ? I.parse : I.parseInline;
	}
}, R = new class {
	defaults = e();
	options = this.setOptions;
	parse = this.parseMarkdown(!0);
	parseInline = this.parseMarkdown(!1);
	Parser = I;
	Renderer = rt;
	TextRenderer = it;
	Lexer = F;
	Tokenizer = nt;
	Hooks = L;
	constructor(...e) {
		this.use(...e);
	}
	walkTokens(e, t) {
		let n = [];
		for (let r of e) switch (n = n.concat(t.call(this, r)), r.type) {
			case "table": {
				let e = r;
				for (let r of e.header) n = n.concat(this.walkTokens(r.tokens, t));
				for (let r of e.rows) for (let e of r) n = n.concat(this.walkTokens(e.tokens, t));
				break;
			}
			case "list": {
				let e = r;
				n = n.concat(this.walkTokens(e.items, t));
				break;
			}
			default: {
				let e = r;
				this.defaults.extensions?.childTokens?.[e.type] ? this.defaults.extensions.childTokens[e.type].forEach((r) => {
					let i = e[r].flat(1 / 0);
					n = n.concat(this.walkTokens(i, t));
				}) : e.tokens && (n = n.concat(this.walkTokens(e.tokens, t)));
			}
		}
		return n;
	}
	use(...e) {
		let t = this.defaults.extensions || {
			renderers: {},
			childTokens: {}
		};
		return e.forEach((e) => {
			let n = { ...e };
			if (n.async = this.defaults.async || n.async || !1, e.extensions && (e.extensions.forEach((e) => {
				if (!e.name) throw Error("extension name required");
				if ("renderer" in e) {
					let n = t.renderers[e.name];
					n ? t.renderers[e.name] = function(...t) {
						let r = e.renderer.apply(this, t);
						return r === !1 && (r = n.apply(this, t)), r;
					} : t.renderers[e.name] = e.renderer;
				}
				if ("tokenizer" in e) {
					if (!e.level || e.level !== "block" && e.level !== "inline") throw Error("extension level must be 'block' or 'inline'");
					let n = t[e.level];
					n ? n.unshift(e.tokenizer) : t[e.level] = [e.tokenizer], e.start && (e.level === "block" ? t.startBlock ? t.startBlock.push(e.start) : t.startBlock = [e.start] : e.level === "inline" && (t.startInline ? t.startInline.push(e.start) : t.startInline = [e.start]));
				}
				"childTokens" in e && e.childTokens && (t.childTokens[e.name] = e.childTokens);
			}), n.extensions = t), e.renderer) {
				let t = this.defaults.renderer || new rt(this.defaults);
				for (let n in e.renderer) {
					if (!(n in t)) throw Error(`renderer '${n}' does not exist`);
					if (["options", "parser"].includes(n)) continue;
					let r = n, i = e.renderer[r], a = t[r];
					t[r] = (...e) => {
						let n = i.apply(t, e);
						return n === !1 && (n = a.apply(t, e)), n || "";
					};
				}
				n.renderer = t;
			}
			if (e.tokenizer) {
				let t = this.defaults.tokenizer || new nt(this.defaults);
				for (let n in e.tokenizer) {
					if (!(n in t)) throw Error(`tokenizer '${n}' does not exist`);
					if ([
						"options",
						"rules",
						"lexer"
					].includes(n)) continue;
					let r = n, i = e.tokenizer[r], a = t[r];
					t[r] = (...e) => {
						let n = i.apply(t, e);
						return n === !1 && (n = a.apply(t, e)), n;
					};
				}
				n.tokenizer = t;
			}
			if (e.hooks) {
				let t = this.defaults.hooks || new L();
				for (let n in e.hooks) {
					if (!(n in t)) throw Error(`hook '${n}' does not exist`);
					if (["options", "block"].includes(n)) continue;
					let r = n, i = e.hooks[r], a = t[r];
					t[r] = L.passThroughHooks.has(n) ? (e) => {
						if (this.defaults.async && L.passThroughHooksRespectAsync.has(n)) return (async () => {
							let n = await i.call(t, e);
							return a.call(t, n);
						})();
						let r = i.call(t, e);
						return a.call(t, r);
					} : (...e) => {
						if (this.defaults.async) return (async () => {
							let n = await i.apply(t, e);
							return n === !1 && (n = await a.apply(t, e)), n;
						})();
						let n = i.apply(t, e);
						return n === !1 && (n = a.apply(t, e)), n;
					};
				}
				n.hooks = t;
			}
			if (e.walkTokens) {
				let t = this.defaults.walkTokens, r = e.walkTokens;
				n.walkTokens = function(e) {
					let n = [];
					return n.push(r.call(this, e)), t && (n = n.concat(t.call(this, e))), n;
				};
			}
			this.defaults = {
				...this.defaults,
				...n
			};
		}), this;
	}
	setOptions(e) {
		return this.defaults = {
			...this.defaults,
			...e
		}, this;
	}
	lexer(e, t) {
		return F.lex(e, t ?? this.defaults);
	}
	parser(e, t) {
		return I.parse(e, t ?? this.defaults);
	}
	parseMarkdown(e) {
		return (t, n) => {
			let r = { ...n }, i = {
				...this.defaults,
				...r
			}, a = this.onError(!!i.silent, !!i.async);
			if (this.defaults.async === !0 && r.async === !1) return a(/* @__PURE__ */ Error("marked(): The async option was set to true by an extension. Remove async: false from the parse options object to return a Promise."));
			if (typeof t > "u" || t === null) return a(/* @__PURE__ */ Error("marked(): input parameter is undefined or null"));
			if (typeof t != "string") return a(/* @__PURE__ */ Error("marked(): input parameter is of type " + Object.prototype.toString.call(t) + ", string expected"));
			if (i.hooks && (i.hooks.options = i, i.hooks.block = e), i.async) return (async () => {
				let n = i.hooks ? await i.hooks.preprocess(t) : t, r = await (i.hooks ? await i.hooks.provideLexer(e) : e ? F.lex : F.lexInline)(n, i), a = i.hooks ? await i.hooks.processAllTokens(r) : r;
				i.walkTokens && await Promise.all(this.walkTokens(a, i.walkTokens));
				let o = await (i.hooks ? await i.hooks.provideParser(e) : e ? I.parse : I.parseInline)(a, i);
				return i.hooks ? await i.hooks.postprocess(o) : o;
			})().catch(a);
			try {
				i.hooks && (t = i.hooks.preprocess(t));
				let n = (i.hooks ? i.hooks.provideLexer(e) : e ? F.lex : F.lexInline)(t, i);
				i.hooks && (n = i.hooks.processAllTokens(n)), i.walkTokens && this.walkTokens(n, i.walkTokens);
				let r = (i.hooks ? i.hooks.provideParser(e) : e ? I.parse : I.parseInline)(n, i);
				return i.hooks && (r = i.hooks.postprocess(r)), r;
			} catch (e) {
				return a(e);
			}
		};
	}
	onError(e, t) {
		return (n) => {
			if (n.message += "\nPlease report this to https://github.com/markedjs/marked.", e) {
				let e = "<p>An error occurred:</p><pre>" + M(n.message + "", !0) + "</pre>";
				return t ? Promise.resolve(e) : e;
			}
			if (t) return Promise.reject(n);
			throw n;
		};
	}
}();
function z(e, t) {
	return R.parse(e, t);
}
z.options = z.setOptions = function(e) {
	return R.setOptions(e), z.defaults = R.defaults, n(z.defaults), z;
}, z.getDefaults = e, z.defaults = t;
function at(...e) {
	return R.use(...e), z.defaults = R.defaults, n(z.defaults), z;
}
z.use = at, z.walkTokens = function(e, t) {
	return R.walkTokens(e, t);
}, z.parseInline = R.parseInline, z.Parser = I, z.parser = I.parse, z.Renderer = rt, z.TextRenderer = it, z.Lexer = F, z.lexer = F.lex, z.Tokenizer = nt, z.Hooks = L, z.parse = z, z.options, z.setOptions, z.walkTokens, z.parseInline, I.parse, F.lex;
//#endregion
//#region node_modules/dompurify/dist/purify.es.mjs
function ot(e, t) {
	this.v = e, this.k = t;
}
function st(e, t) {
	(t == null || t > e.length) && (t = e.length);
	for (var n = 0, r = Array(t); n < t; n++) r[n] = e[n];
	return r;
}
function ct(e) {
	if (Array.isArray(e)) return e;
}
function lt(e, t) {
	var n = e == null ? null : typeof Symbol < "u" && e[Symbol.iterator] || e["@@iterator"];
	if (n != null) {
		var r, i, a, o, s = [], c = !0, l = !1;
		try {
			if (a = (n = n.call(e)).next, t === 0) {
				if (Object(n) !== n) return;
				c = !1;
			} else for (; !(c = (r = a.call(n)).done) && (s.push(r.value), s.length !== t); c = !0);
		} catch (e) {
			l = !0, i = e;
		} finally {
			try {
				if (!c && n.return != null && (o = n.return(), Object(o) !== o)) return;
			} finally {
				if (l) throw i;
			}
		}
		return s;
	}
}
function ut() {
	throw TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function dt(e, t) {
	return ct(e) || lt(e, t) || ft(e, t) || ut();
}
function ft(e, t) {
	if (e) {
		if (typeof e == "string") return st(e, t);
		var n = {}.toString.call(e).slice(8, -1);
		return n === "Object" && e.constructor && (n = e.constructor.name), n === "Map" || n === "Set" ? Array.from(e) : n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n) ? st(e, t) : void 0;
	}
}
function pt(e) {
	var t, n;
	function r(t, n) {
		try {
			var a = e[t](n), o = a.value, s = o instanceof ot;
			Promise.resolve(s ? o.v : o).then(function(n) {
				if (s) {
					var c = t === "return" && o.k ? t : "next";
					if (!o.k || n.done) return r(c, n);
					n = e[c](n).value;
				}
				i(!!a.done, n);
			}, function(e) {
				r("throw", e);
			});
		} catch (e) {
			i(2, e);
		}
	}
	function i(e, i) {
		e === 2 ? t.reject(i) : t.resolve({
			value: i,
			done: e
		}), (t = t.next) ? r(t.key, t.arg) : n = null;
	}
	this._invoke = function(e, i) {
		return new Promise(function(a, o) {
			var s = {
				key: e,
				arg: i,
				resolve: a,
				reject: o,
				next: null
			};
			n ? n = n.next = s : (t = n = s, r(e, i));
		});
	}, typeof e.return != "function" && (this.return = void 0);
}
pt.prototype[typeof Symbol == "function" && Symbol.asyncIterator || "@@asyncIterator"] = function() {
	return this;
}, pt.prototype.next = function(e) {
	return this._invoke("next", e);
}, pt.prototype.throw = function(e) {
	return this._invoke("throw", e);
}, pt.prototype.return = function(e) {
	return this._invoke("return", e);
};
var mt = Object.entries, ht = Object.setPrototypeOf, B = Object.isFrozen, gt = Object.getPrototypeOf, _t = Object.getOwnPropertyDescriptor, V = Object.freeze, H = Object.seal, vt = Object.create, U = typeof Reflect < "u" && Reflect, yt = U.apply, bt = U.construct;
V ||= function(e) {
	return e;
}, H ||= function(e) {
	return e;
}, yt ||= function(e, t) {
	var n = [...arguments].slice(2);
	return e.apply(t, n);
}, bt ||= function(e) {
	return new e(...[...arguments].slice(1));
};
var xt = J(Array.prototype.forEach);
Array.prototype.indexOf;
var St = J(Array.prototype.lastIndexOf), Ct = J(Array.prototype.pop), wt = J(Array.prototype.push);
Array.prototype.slice;
var Tt = J(Array.prototype.splice), Et = Array.isArray, Dt = J(String.prototype.toLowerCase), Ot = J(String.prototype.toString), kt = J(String.prototype.match), At = J(String.prototype.replace), jt = J(String.prototype.indexOf), Mt = J(String.prototype.trim), Nt = J(Number.prototype.toString), Pt = J(Boolean.prototype.toString), Ft = typeof BigInt > "u" ? null : J(BigInt.prototype.toString), It = typeof Symbol > "u" ? null : J(Symbol.prototype.toString), W = J(Object.prototype.hasOwnProperty), G = J(Object.prototype.toString), K = J(RegExp.prototype.test), q = Lt(TypeError);
function J(e) {
	return function(t) {
		t instanceof RegExp && (t.lastIndex = 0);
		var n = [...arguments].slice(1);
		return yt(e, t, n);
	};
}
function Lt(e) {
	return function() {
		return bt(e, [...arguments]);
	};
}
function Y(e, t) {
	let n = arguments.length > 2 && arguments[2] !== void 0 ? arguments[2] : Dt;
	if (ht && ht(e, null), !Et(t)) return e;
	let r = t.length;
	for (; r--;) {
		let i = t[r];
		if (typeof i == "string") {
			let e = n(i);
			e !== i && (B(t) || (t[r] = e), i = e);
		}
		e[i] = !0;
	}
	return e;
}
function Rt(e) {
	for (let t = 0; t < e.length; t++) W(e, t) || (e[t] = null);
	return e;
}
function X(e) {
	let t = vt(null);
	for (let r of mt(e)) {
		var n = dt(r, 2);
		let i = n[0], a = n[1];
		W(e, i) && (t[i] = Et(a) ? Rt(a) : a && typeof a == "object" && a.constructor === Object ? X(a) : a);
	}
	return t;
}
function zt(e) {
	switch (typeof e) {
		case "string": return e;
		case "number": return Nt(e);
		case "boolean": return Pt(e);
		case "bigint": return Ft ? Ft(e) : "0";
		case "symbol": return It ? It(e) : "Symbol()";
		case "undefined": return G(e);
		case "function":
		case "object": {
			if (e === null) return G(e);
			let t = e, n = Z(t, "toString");
			if (typeof n == "function") {
				let e = n(t);
				return typeof e == "string" ? e : G(e);
			}
			return G(e);
		}
		default: return G(e);
	}
}
function Z(e, t) {
	for (; e !== null;) {
		let n = _t(e, t);
		if (n) {
			if (n.get) return J(n.get);
			if (typeof n.value == "function") return J(n.value);
		}
		e = gt(e);
	}
	function n() {
		return null;
	}
	return n;
}
function Bt(e) {
	try {
		return K(e, ""), !0;
	} catch {
		return !1;
	}
}
var Vt = V(/* @__PURE__ */ "a.abbr.acronym.address.area.article.aside.audio.b.bdi.bdo.big.blink.blockquote.body.br.button.canvas.caption.center.cite.code.col.colgroup.content.data.datalist.dd.decorator.del.details.dfn.dialog.dir.div.dl.dt.element.em.fieldset.figcaption.figure.font.footer.form.h1.h2.h3.h4.h5.h6.head.header.hgroup.hr.html.i.img.input.ins.kbd.label.legend.li.main.map.mark.marquee.menu.menuitem.meter.nav.nobr.ol.optgroup.option.output.p.picture.pre.progress.q.rp.rt.ruby.s.samp.search.section.select.shadow.slot.small.source.spacer.span.strike.strong.style.sub.summary.sup.table.tbody.td.template.textarea.tfoot.th.thead.time.tr.track.tt.u.ul.var.video.wbr".split(".")), Ht = V(/* @__PURE__ */ "svg.a.altglyph.altglyphdef.altglyphitem.animatecolor.animatemotion.animatetransform.circle.clippath.defs.desc.ellipse.enterkeyhint.exportparts.filter.font.g.glyph.glyphref.hkern.image.inputmode.line.lineargradient.marker.mask.metadata.mpath.part.path.pattern.polygon.polyline.radialgradient.rect.stop.style.switch.symbol.text.textpath.title.tref.tspan.view.vkern".split(".")), Ut = V([
	"feBlend",
	"feColorMatrix",
	"feComponentTransfer",
	"feComposite",
	"feConvolveMatrix",
	"feDiffuseLighting",
	"feDisplacementMap",
	"feDistantLight",
	"feDropShadow",
	"feFlood",
	"feFuncA",
	"feFuncB",
	"feFuncG",
	"feFuncR",
	"feGaussianBlur",
	"feImage",
	"feMerge",
	"feMergeNode",
	"feMorphology",
	"feOffset",
	"fePointLight",
	"feSpecularLighting",
	"feSpotLight",
	"feTile",
	"feTurbulence"
]), Wt = V([
	"animate",
	"color-profile",
	"cursor",
	"discard",
	"font-face",
	"font-face-format",
	"font-face-name",
	"font-face-src",
	"font-face-uri",
	"foreignobject",
	"hatch",
	"hatchpath",
	"mesh",
	"meshgradient",
	"meshpatch",
	"meshrow",
	"missing-glyph",
	"script",
	"set",
	"solidcolor",
	"unknown",
	"use"
]), Gt = V(/* @__PURE__ */ "math.menclose.merror.mfenced.mfrac.mglyph.mi.mlabeledtr.mmultiscripts.mn.mo.mover.mpadded.mphantom.mroot.mrow.ms.mspace.msqrt.mstyle.msub.msup.msubsup.mtable.mtd.mtext.mtr.munder.munderover.mprescripts".split(".")), Kt = V([
	"maction",
	"maligngroup",
	"malignmark",
	"mlongdiv",
	"mscarries",
	"mscarry",
	"msgroup",
	"mstack",
	"msline",
	"msrow",
	"semantics",
	"annotation",
	"annotation-xml",
	"mprescripts",
	"none"
]), qt = V(["#text"]), Jt = V(/* @__PURE__ */ "accept.action.align.alt.autocapitalize.autocomplete.autopictureinpicture.autoplay.background.bgcolor.border.capture.cellpadding.cellspacing.checked.cite.class.clear.color.cols.colspan.command.commandfor.controls.controlslist.coords.crossorigin.datetime.decoding.default.dir.disabled.disablepictureinpicture.disableremoteplayback.download.draggable.enctype.enterkeyhint.exportparts.face.for.headers.height.hidden.high.href.hreflang.id.inert.inputmode.integrity.ismap.kind.label.lang.list.loading.loop.low.max.maxlength.media.method.min.minlength.multiple.muted.name.nonce.noshade.novalidate.nowrap.open.optimum.part.pattern.placeholder.playsinline.popover.popovertarget.popovertargetaction.poster.preload.pubdate.radiogroup.readonly.rel.required.rev.reversed.role.rows.rowspan.spellcheck.scope.selected.shape.size.sizes.slot.span.srclang.start.src.srcset.step.style.summary.tabindex.title.translate.type.usemap.valign.value.width.wrap.xmlns".split(".")), Yt = V(/* @__PURE__ */ "accent-height.accumulate.additive.alignment-baseline.amplitude.ascent.attributename.attributetype.azimuth.basefrequency.baseline-shift.begin.bias.by.class.clip.clippathunits.clip-path.clip-rule.color.color-interpolation.color-interpolation-filters.color-profile.color-rendering.cx.cy.d.dx.dy.diffuseconstant.direction.display.divisor.dominant-baseline.dur.edgemode.elevation.end.exponent.fill.fill-opacity.fill-rule.filter.filterunits.flood-color.flood-opacity.font-family.font-size.font-size-adjust.font-stretch.font-style.font-variant.font-weight.fx.fy.g1.g2.glyph-name.glyphref.gradientunits.gradienttransform.height.href.id.image-rendering.in.in2.intercept.k.k1.k2.k3.k4.kerning.keypoints.keysplines.keytimes.lang.lengthadjust.letter-spacing.kernelmatrix.kernelunitlength.lighting-color.local.marker-end.marker-mid.marker-start.markerheight.markerunits.markerwidth.maskcontentunits.maskunits.max.mask.mask-type.media.method.mode.min.name.numoctaves.offset.operator.opacity.order.orient.orientation.origin.overflow.paint-order.path.pathlength.patterncontentunits.patterntransform.patternunits.pointer-events.points.preservealpha.preserveaspectratio.primitiveunits.r.rx.ry.radius.refx.refy.repeatcount.repeatdur.restart.result.rotate.scale.seed.shape-rendering.slope.specularconstant.specularexponent.spreadmethod.startoffset.stddeviation.stitchtiles.stop-color.stop-opacity.stroke-dasharray.stroke-dashoffset.stroke-linecap.stroke-linejoin.stroke-miterlimit.stroke-opacity.stroke.stroke-width.style.surfacescale.systemlanguage.tabindex.tablevalues.targetx.targety.transform.transform-origin.text-anchor.text-decoration.text-orientation.text-rendering.textlength.type.u1.u2.unicode.values.vector-effect.viewbox.visibility.version.vert-adv-y.vert-origin-x.vert-origin-y.width.word-spacing.wrap.writing-mode.xchannelselector.ychannelselector.x.x1.x2.xmlns.y.y1.y2.z.zoomandpan".split(".")), Xt = V(/* @__PURE__ */ "accent.accentunder.align.bevelled.close.columnalign.columnlines.columnspacing.columnspan.denomalign.depth.dir.display.displaystyle.encoding.fence.frame.height.href.id.largeop.length.linethickness.lquote.lspace.mathbackground.mathcolor.mathsize.mathvariant.maxsize.minsize.movablelimits.notation.numalign.open.rowalign.rowlines.rowspacing.rowspan.rspace.rquote.scriptlevel.scriptminsize.scriptsizemultiplier.selection.separator.separators.stretchy.subscriptshift.supscriptshift.symmetric.voffset.width.xmlns".split(".")), Zt = V([
	"xlink:href",
	"xml:id",
	"xlink:title",
	"xml:space",
	"xmlns:xlink"
]), Qt = H(/{{[\w\W]*|^[\w\W]*}}/g), $t = H(/<%[\w\W]*|^[\w\W]*%>/g), en = H(/\${[\w\W]*/g), tn = H(/^data-[\-\w.\u00B7-\uFFFF]+$/), nn = H(/^aria-[\-\w]+$/), rn = H(/^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|matrix):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i), an = H(/^(?:\w+script|data):/i), on = H(/[\u0000-\u0020\u00A0\u1680\u180E\u2000-\u2029\u205F\u3000]/g), sn = H(/^html$/i), cn = H(/^[a-z][.\w]*(-[.\w]+)+$/i), ln = H(/<[/\w!]/g), un = H(/<[/\w]/g), dn = H(/<\/no(script|embed|frames)/i), fn = H(/\/>/i), Q = {
	element: 1,
	attribute: 2,
	text: 3,
	cdataSection: 4,
	entityReference: 5,
	entityNode: 6,
	processingInstruction: 7,
	comment: 8,
	document: 9,
	documentType: 10,
	documentFragment: 11,
	notation: 12
}, pn = [
	"style",
	"script",
	"xmp",
	"iframe",
	"noembed",
	"noframes",
	"plaintext",
	"noscript"
], mn = V(Y({}, pn)), hn = function() {
	let e = {};
	return xt(pn, (t) => {
		e[t] = H(RegExp("</" + t + "(?=[\\t\\n\\f\\r />])", "i"));
	}), V(e);
}(), gn = function() {
	return typeof window > "u" ? null : window;
}, _n = function(e, t) {
	if (typeof e != "object" || typeof e.createPolicy != "function") return null;
	let n = null, r = "data-tt-policy-suffix";
	t && t.hasAttribute(r) && (n = t.getAttribute(r));
	let i = "dompurify" + (n ? "#" + n : "");
	try {
		return e.createPolicy(i, {
			createHTML(e) {
				return e;
			},
			createScriptURL(e) {
				return e;
			}
		});
	} catch {
		return console.warn("TrustedTypes policy " + i + " could not be created."), null;
	}
}, vn = function() {
	return {
		afterSanitizeAttributes: [],
		afterSanitizeElements: [],
		afterSanitizeShadowDOM: [],
		beforeSanitizeAttributes: [],
		beforeSanitizeElements: [],
		beforeSanitizeShadowDOM: [],
		uponSanitizeAttribute: [],
		uponSanitizeElement: [],
		uponSanitizeShadowNode: []
	};
}, yn = function(e, t, n, r) {
	return W(e, t) && Et(e[t]) ? Y(r.base ? X(r.base) : {}, e[t], r.transform) : n;
}, bn = function(e, t, n) {
	let r = W(e, t) ? e[t] : void 0;
	return r && typeof r == "object" ? X(r) : n();
};
function xn() {
	let e = arguments.length > 0 && arguments[0] !== void 0 ? arguments[0] : gn(), t = (e) => xn(e);
	if (t.version = "3.4.16", t.removed = [], !e || !e.document || e.document.nodeType !== Q.document || !e.Element) return t.isSupported = !1, t;
	let n = e.document, r = n, i = r.currentScript;
	e.DocumentFragment;
	let a = e.HTMLTemplateElement, o = e.Node, s = e.Element, c = e.NodeFilter;
	e.NamedNodeMap === void 0 && (e.NamedNodeMap || e.MozNamedAttrMap), e.HTMLFormElement;
	let l = e.DOMParser, u = e.trustedTypes, d = s.prototype, f = Z(d, "cloneNode"), p = Z(d, "remove"), m = Z(d, "removeAttributeNode"), ee = Z(d, "nextSibling"), te = Z(d, "childNodes"), h = Z(d, "parentNode"), ne = Z(d, "shadowRoot"), re = Z(d, "attributes"), g = o && o.prototype ? Z(o.prototype, "nodeType") : null, ie = o && o.prototype ? Z(o.prototype, "nodeName") : null, _ = o && o.prototype ? Z(o.prototype, "ownerDocument") : null, v = function(e) {
		return g ? g(e) : e.nodeType;
	}, ae = function(e) {
		return ie ? ie(e) : e.nodeName;
	};
	if (typeof a == "function") {
		let e = n.createElement("template");
		e.content && e.content.ownerDocument && (n = e.content.ownerDocument);
	}
	let y, b = "", oe, se = !1, ce = 0, le = function() {
		if (ce > 0) throw q("A configured TRUSTED_TYPES_POLICY callback (createHTML or createScriptURL) must not call DOMPurify.sanitize, as that causes infinite recursion. Do not pass a policy whose callbacks wrap DOMPurify as TRUSTED_TYPES_POLICY; see the \"DOMPurify and Trusted Types\" section of the README.");
	}, ue = function(e) {
		le(), ce++;
		try {
			return y.createHTML(e);
		} finally {
			ce--;
		}
	}, de = function(e) {
		le(), ce++;
		try {
			return y.createScriptURL(e);
		} finally {
			ce--;
		}
	}, fe = function() {
		return se ||= (oe = _n(u, i), !0), oe;
	}, pe = n, me = pe.implementation, x = pe.createNodeIterator, he = pe.createDocumentFragment, ge = pe.getElementsByTagName, _e = r.importNode, S = vn();
	t.isSupported = typeof mt == "function" && typeof h == "function" && me && me.createHTMLDocument !== void 0;
	let ve = Qt, ye = $t, be = en, xe = tn, Se = nn, Ce = an, we = on, Te = cn, Ee = rn, C = null, De = Y({}, [
		...Vt,
		...Ht,
		...Ut,
		...Gt,
		...qt
	]), w = null, Oe = Y({}, [
		...Jt,
		...Yt,
		...Xt,
		...Zt
	]), T = Object.seal(vt(null, {
		tagNameCheck: {
			writable: !0,
			configurable: !1,
			enumerable: !0,
			value: null
		},
		attributeNameCheck: {
			writable: !0,
			configurable: !1,
			enumerable: !0,
			value: null
		},
		allowCustomizedBuiltInElements: {
			writable: !0,
			configurable: !1,
			enumerable: !0,
			value: !1
		}
	})), ke = null, Ae = null, E = Object.seal(vt(null, {
		tagCheck: {
			writable: !0,
			configurable: !1,
			enumerable: !0,
			value: null
		},
		attributeCheck: {
			writable: !0,
			configurable: !1,
			enumerable: !0,
			value: null
		}
	})), je = !0, Me = !0, Ne = !1, Pe = !0, D = !1, Fe = !0, O = !1, Ie = !1, Le = null, Re = null, ze = !1, k = !1, Be = !1, Ve = !1, He = !0, Ue = !1, We = "user-content-", Ge = !0, A = !1, Ke = {}, j = null, M = Y({}, /* @__PURE__ */ "annotation-xml.audio.colgroup.desc.foreignobject.head.iframe.math.mi.mn.mo.ms.mtext.noembed.noframes.noscript.plaintext.script.selectedcontent.style.svg.template.thead.title.video.xmp".split(".")), qe = null, Je = Y({}, [
		"audio",
		"video",
		"img",
		"source",
		"image",
		"track"
	]), Ye = null, N = Y({}, [
		"alt",
		"class",
		"for",
		"id",
		"label",
		"name",
		"pattern",
		"placeholder",
		"role",
		"summary",
		"title",
		"value",
		"style",
		"xmlns"
	]), Xe = "http://www.w3.org/1998/Math/MathML", Ze = "http://www.w3.org/2000/svg", P = "http://www.w3.org/1999/xhtml", Qe = P, $e = !1, et = null, tt = Y({}, [
		Xe,
		Ze,
		P
	], Ot), nt = V([
		"mi",
		"mo",
		"mn",
		"ms",
		"mtext"
	]), F = Y({}, nt), rt = V(["annotation-xml"]), it = Y({}, rt), I = Y({}, [
		"title",
		"style",
		"font",
		"a",
		"script"
	]), L = null, R = ["application/xhtml+xml", "text/html"], z = null, at = null, ot = n.createElement("form"), st = function(e) {
		return e instanceof RegExp || e instanceof Function;
	}, ct = function() {
		let e = arguments.length > 0 && arguments[0] !== void 0 ? arguments[0] : {};
		if (at && at === e) return;
		(!e || typeof e != "object") && (e = {}), e = X(e), L = R.indexOf(e.PARSER_MEDIA_TYPE) === -1 ? "text/html" : e.PARSER_MEDIA_TYPE, z = L === "application/xhtml+xml" ? Ot : Dt, C = yn(e, "ALLOWED_TAGS", De, { transform: z }), w = yn(e, "ALLOWED_ATTR", Oe, { transform: z }), et = yn(e, "ALLOWED_NAMESPACES", tt, { transform: Ot }), Ye = yn(e, "ADD_URI_SAFE_ATTR", N, {
			transform: z,
			base: N
		}), qe = yn(e, "ADD_DATA_URI_TAGS", Je, {
			transform: z,
			base: Je
		}), j = yn(e, "FORBID_CONTENTS", M, { transform: z }), ke = yn(e, "FORBID_TAGS", X({}), { transform: z }), Ae = yn(e, "FORBID_ATTR", X({}), { transform: z }), Ke = W(e, "USE_PROFILES") ? e.USE_PROFILES && typeof e.USE_PROFILES == "object" ? X(e.USE_PROFILES) : e.USE_PROFILES : !1, je = e.ALLOW_ARIA_ATTR !== !1, Me = e.ALLOW_DATA_ATTR !== !1, Ne = e.ALLOW_UNKNOWN_PROTOCOLS || !1, Pe = e.ALLOW_SELF_CLOSE_IN_ATTR !== !1, D = e.SAFE_FOR_TEMPLATES || !1, Fe = e.SAFE_FOR_XML !== !1, O = e.WHOLE_DOCUMENT || !1, k = e.RETURN_DOM || !1, Be = e.RETURN_DOM_FRAGMENT || !1, Ve = e.RETURN_TRUSTED_TYPE || !1, ze = e.FORCE_BODY || !1, He = e.SANITIZE_DOM !== !1, Ue = e.SANITIZE_NAMED_PROPS || !1, Ge = e.KEEP_CONTENT !== !1, A = e.IN_PLACE || !1, Ee = Bt(e.ALLOWED_URI_REGEXP) ? e.ALLOWED_URI_REGEXP : rn, Qe = typeof e.NAMESPACE == "string" ? e.NAMESPACE : P, F = bn(e, "MATHML_TEXT_INTEGRATION_POINTS", () => Y({}, nt)), it = bn(e, "HTML_INTEGRATION_POINTS", () => Y({}, rt));
		let t = bn(e, "CUSTOM_ELEMENT_HANDLING", () => vt(null));
		if (T = vt(null), W(t, "tagNameCheck") && st(t.tagNameCheck) && (T.tagNameCheck = t.tagNameCheck), W(t, "attributeNameCheck") && st(t.attributeNameCheck) && (T.attributeNameCheck = t.attributeNameCheck), W(t, "allowCustomizedBuiltInElements") && typeof t.allowCustomizedBuiltInElements == "boolean" && (T.allowCustomizedBuiltInElements = t.allowCustomizedBuiltInElements), H(T), D && (Me = !1), Be && (k = !0), Ke && (C = Y({}, qt), w = vt(null), Ke.html === !0 && (Y(C, Vt), Y(w, Jt)), Ke.svg === !0 && (Y(C, Ht), Y(w, Yt), Y(w, Zt)), Ke.svgFilters === !0 && (Y(C, Ut), Y(w, Yt), Y(w, Zt)), Ke.mathMl === !0 && (Y(C, Gt), Y(w, Xt), Y(w, Zt))), E.tagCheck = null, E.attributeCheck = null, W(e, "ADD_TAGS") && (typeof e.ADD_TAGS == "function" ? E.tagCheck = e.ADD_TAGS : Et(e.ADD_TAGS) && (C === De && (C = X(C)), Y(C, e.ADD_TAGS, z))), W(e, "ADD_ATTR") && (typeof e.ADD_ATTR == "function" ? E.attributeCheck = e.ADD_ATTR : Et(e.ADD_ATTR) && (w === Oe && (w = X(w)), Y(w, e.ADD_ATTR, z))), W(e, "ADD_FORBID_CONTENTS") && Et(e.ADD_FORBID_CONTENTS) && (j === M && (j = X(j)), Y(j, e.ADD_FORBID_CONTENTS, z)), Ge && (C["#text"] = !0), O && Y(C, [
			"html",
			"head",
			"body"
		]), C.table && (Y(C, ["tbody"]), delete ke.tbody), e.TRUSTED_TYPES_POLICY) {
			if (typeof e.TRUSTED_TYPES_POLICY.createHTML != "function") throw q("TRUSTED_TYPES_POLICY configuration option must provide a \"createHTML\" hook.");
			if (typeof e.TRUSTED_TYPES_POLICY.createScriptURL != "function") throw q("TRUSTED_TYPES_POLICY configuration option must provide a \"createScriptURL\" hook.");
			let t = y;
			y = e.TRUSTED_TYPES_POLICY;
			try {
				b = ue("");
			} catch (e) {
				throw y = t, e;
			}
		} else e.TRUSTED_TYPES_POLICY === null ? (y = void 0, b = "") : (y === void 0 && (y = fe()), y && typeof b == "string" && (b = ue("")));
		V && V(e), at = e;
	}, lt = Y({}, [
		...Ht,
		...Ut,
		...Wt
	]), ut = Y({}, [...Gt, ...Kt]), dt = function(e, t, n) {
		return t.namespaceURI === P ? e === "svg" : t.namespaceURI === Xe ? e === "svg" && (n === "annotation-xml" || F[n]) : !!lt[e];
	}, ft = function(e, t, n) {
		return t.namespaceURI === P ? e === "math" : t.namespaceURI === Ze ? e === "math" && it[n] : !!ut[e];
	}, pt = function(e, t, n) {
		return t.namespaceURI === Ze && !it[n] || t.namespaceURI === Xe && !F[n] ? !1 : !ut[e] && (I[e] || !lt[e]);
	}, ht = function(e) {
		let t = h(e);
		(!t || !t.tagName) && (t = {
			namespaceURI: Qe,
			tagName: "template"
		});
		let n = Dt(e.tagName), r = Dt(t.tagName);
		return et[e.namespaceURI] ? e.namespaceURI === Ze ? dt(n, t, r) : e.namespaceURI === Xe ? ft(n, t, r) : e.namespaceURI === P ? pt(n, t, r) : !!(L === "application/xhtml+xml" && et[e.namespaceURI]) : !1;
	}, B = function(e) {
		wt(t.removed, { element: e });
		try {
			h(e).removeChild(e);
		} catch {
			if (p(e), !h(e)) throw q("a node selected for removal could not be detached from its tree and cannot be safely returned; refusing to sanitize in place");
		}
	}, gt = function(e, t, n) {
		try {
			m(e, t);
		} catch {
			try {
				e.removeAttribute(n);
			} catch {}
		}
	}, _t = function(e) {
		bt(e);
		let t = te(e);
		if (t) {
			let e = [];
			xt(t, (t) => {
				wt(e, t);
			}), xt(e, (e) => {
				try {
					p(e);
				} catch {}
			});
		}
		let n = re(e);
		if (n) for (let t = n.length - 1; t >= 0; --t) {
			let r = n[t], i = r && r.name;
			typeof i == "string" && gt(e, r, i);
		}
	}, U = function(e, n, r) {
		if (!r) try {
			r = n.getAttributeNode(e);
		} catch {
			r = null;
		}
		wt(t.removed, {
			attribute: r || null,
			from: n
		});
		try {
			r ? m(n, r) : n.removeAttribute(e);
		} catch {
			try {
				n.removeAttribute(e);
			} catch {}
		}
		if (e === "is") {
			if (k || Be) try {
				B(n);
			} catch {}
			else try {
				n.setAttribute(e, "");
			} catch {}
		}
	}, yt = function(e) {
		let t = re(e);
		if (t) for (let n = t.length - 1; n >= 0; --n) {
			let r = t[n], i = r && r.name;
			typeof i != "string" || w[z(i)] || gt(e, r, i);
		}
	}, bt = function(e) {
		let t = [e];
		for (; t.length > 0;) {
			let e = t.pop();
			v(e) === Q.element && yt(e);
			let n = te(e);
			if (n) for (let e = n.length - 1; e >= 0; --e) t.push(n[e]);
		}
	}, Nt = function(e, t) {
		return Fe ? e === "patchsrc" || e === "for" && t !== "label" && t !== "output" : !1;
	}, Pt = function(e) {
		if (!Fe) return;
		let t = [e];
		for (; t.length > 0;) {
			let e = t.pop(), n = v(e);
			if (n === Q.processingInstruction || n === Q.comment && K(un, e.data)) {
				try {
					p(e);
				} catch {}
				continue;
			}
			if (n === Q.element) {
				let t = e, n = z(ae(e));
				try {
					t.hasAttribute && t.hasAttribute("patchsrc") && t.removeAttribute("patchsrc"), t.hasAttribute && t.hasAttribute("for") && Nt("for", n) && t.removeAttribute("for");
				} catch {}
			}
			let r = te(e);
			if (r) for (let e = r.length - 1; e >= 0; --e) t.push(r[e]);
		}
	}, Ft = function(e) {
		let t = null, r = null;
		if (ze) e = "<remove></remove>" + e;
		else {
			let t = kt(e, /^[\r\n\t ]+/);
			r = t && t[0];
		}
		L === "application/xhtml+xml" && Qe === P && (e = "<html xmlns=\"http://www.w3.org/1999/xhtml\"><head></head><body>" + e + "</body></html>");
		let i = y ? ue(e) : e;
		if (Qe === P) try {
			t = new l().parseFromString(i, L);
		} catch {}
		if (!t || !t.documentElement) {
			t = me.createDocument(Qe, "template", null);
			try {
				t.documentElement.innerHTML = $e ? b : i;
			} catch {}
		}
		let a = t.body || t.documentElement;
		return e && r && a.insertBefore(n.createTextNode(r), a.childNodes[0] || null), Qe === P ? ge.call(t, O ? "html" : "body")[0] : O ? t.documentElement : a;
	}, It = function(e) {
		let t = _ ? _(e) : e.ownerDocument;
		return x.call(t || e, e, c.SHOW_ELEMENT | c.SHOW_COMMENT | c.SHOW_TEXT | c.SHOW_PROCESSING_INSTRUCTION | c.SHOW_CDATA_SECTION, null);
	}, G = function(e) {
		return e = At(e, ve, " "), e = At(e, ye, " "), e = At(e, be, " "), e;
	}, J = function(e) {
		e.normalize();
		let t = _ ? _(e) : e.ownerDocument, n = x.call(t || e, e, c.SHOW_TEXT | c.SHOW_COMMENT | c.SHOW_CDATA_SECTION | c.SHOW_PROCESSING_INSTRUCTION, null), r = n.nextNode();
		for (; r;) r.data = G(r.data), r = n.nextNode();
		let i = e.querySelectorAll?.call(e, "template");
		i && xt(i, (e) => {
			Rt(e.content) && J(e.content);
		});
	}, Lt = function(e) {
		let t = ie ? ie(e) : null;
		return typeof t != "string" || z(t) !== "form" ? !1 : typeof e.nodeName != "string" || typeof e.textContent != "string" || typeof e.removeChild != "function" || e.attributes !== re(e) || typeof e.removeAttribute != "function" || typeof e.removeAttributeNode != "function" || typeof e.getAttributeNode != "function" || typeof e.setAttribute != "function" || typeof e.namespaceURI != "string" || typeof e.insertBefore != "function" || typeof e.hasChildNodes != "function" || e.nodeType !== g(e) || e.childNodes !== te(e);
	}, Rt = function(e) {
		if (!g || typeof e != "object" || !e) return !1;
		try {
			return g(e) === Q.documentFragment;
		} catch {
			return !1;
		}
	}, pn = function(e) {
		if (!g || typeof e != "object" || !e) return !1;
		try {
			return typeof g(e) == "number";
		} catch {
			return !1;
		}
	};
	function $(e, n, r) {
		e.length !== 0 && xt(e, (e) => {
			e.call(t, n, r, at);
		});
	}
	let Sn = function(e, t) {
		return !!(Fe && e.hasChildNodes() && !pn(e.firstElementChild) && K(ln, e.textContent) && K(ln, e.innerHTML) || Fe && e.namespaceURI === P && mn[t] && (pn(e.firstElementChild) || typeof e.textContent == "string" && K(hn[t], e.textContent)) || e.nodeType === Q.processingInstruction || Fe && e.nodeType === Q.comment && K(un, e.data));
	}, Cn = function(e, t) {
		return e instanceof RegExp ? K(e, t) : e instanceof Function && !!e(t, ...[...arguments].slice(2));
	}, wn = function(e, t, n) {
		if (!ke[t] && An(t) && Cn(T.tagNameCheck, t)) return !1;
		if (Ge && !j[t]) {
			let t = h(e), r = te(e);
			if (r && t) {
				let i = r.length;
				for (let a = i - 1; a >= 0; --a) {
					let i = e === n ? f(r[a], !0) : r[a];
					t.insertBefore(i, ee(e));
				}
			}
		}
		return B(e), !0;
	}, Tn = function(e, t, n, r) {
		return e.length === 0 ? t : t === n || t === r ? X(t) : t;
	}, En = function(e, t) {
		return e === t || h(e) !== null ? !1 : (A && bt(e), !0);
	}, Dn = function(e, n) {
		if ($(S.beforeSanitizeElements, e, null), En(e, n)) return !0;
		if (Lt(e)) return B(e), !0;
		let r = z(ae(e));
		if (C = Tn(S.uponSanitizeElement, C, De, Le), $(S.uponSanitizeElement, e, {
			tagName: r,
			allowedTags: C
		}), En(e, n)) return !0;
		if (Sn(e, r)) return B(e), !0;
		if (ke[r] || !(E.tagCheck instanceof Function && E.tagCheck(r)) && !C[r]) {
			let t = wn(e, r, n);
			return t === !1 && ($(S.afterSanitizeElements, e, null), En(e, n)) ? !0 : t;
		}
		if (v(e) === Q.element && !ht(e) || (r === "noscript" || r === "noembed" || r === "noframes") && K(dn, e.innerHTML)) return B(e), !0;
		if (D && e.nodeType === Q.text) {
			let n = G(e.textContent);
			e.textContent !== n && (wt(t.removed, { element: e.cloneNode() }), e.textContent = n);
		}
		return $(S.afterSanitizeElements, e, null), En(e, n);
	}, On = function(e, t, r) {
		if (Ae[t] || Nt(t, e) || He && (t === "id" || t === "name") && (r in n || r in ot)) return !1;
		let i = w[t] || E.attributeCheck instanceof Function && E.attributeCheck(t, e);
		return Me && K(xe, t) || je && K(Se, t) ? !0 : i ? Ye[t] || K(Ee, At(r, we, "")) || (t === "src" || t === "xlink:href" || t === "href") && e !== "script" && jt(r, "data:") === 0 && qe[e] || Ne && !K(Ce, At(r, we, "")) ? !0 : !r : An(e) && Cn(T.tagNameCheck, e) && Cn(T.attributeNameCheck, t, e) || t === "is" && T.allowCustomizedBuiltInElements && Cn(T.tagNameCheck, r);
	}, kn = Y({}, [
		"annotation-xml",
		"color-profile",
		"font-face",
		"font-face-format",
		"font-face-name",
		"font-face-src",
		"font-face-uri",
		"missing-glyph"
	]), An = function(e) {
		return !kn[Dt(e)] && K(Te, e);
	}, jn = function(e, t, n, r) {
		if (y && typeof u == "object" && typeof u.getAttributeType == "function" && !n) switch (u.getAttributeType(e, t)) {
			case "TrustedHTML": return ue(r);
			case "TrustedScriptURL": return de(r);
		}
		return r;
	}, Mn = function(e, t, n, r) {
		try {
			return n ? e.setAttributeNS(n, t, r) : e.setAttribute(t, r), !Lt(e) || (B(e), !1);
		} catch {
			return U(t, e), !1;
		}
	}, Nn = function(e, n) {
		if ($(S.beforeSanitizeAttributes, e, null), En(e, n)) return;
		let r = e.attributes;
		if (!r || Lt(e)) return;
		w = Tn(S.uponSanitizeAttribute, w, Oe, Re);
		let i = {
			attrName: "",
			attrValue: "",
			keepAttr: !0,
			allowedAttributes: w,
			forceKeepAttr: void 0
		}, a = r.length, o = z(e.nodeName);
		for (; a--;) {
			let n = r[a], s = n.name, c = n.namespaceURI, l = n.value, u = z(s), d = l, f = s === "value" ? d : Mt(d), p = !1;
			if (i.attrName = u, i.attrValue = f, i.keepAttr = !0, i.forceKeepAttr = void 0, $(S.uponSanitizeAttribute, e, i), f = i.attrValue, Ue && (u === "id" || u === "name") && jt(f, We) !== 0 && (U(s, e, n), f = We + f, p = !0), Fe && K(/((--!?|])>)|<\/(style|script|title|xmp|textarea|noscript|iframe|noembed|noframes)/i, f)) {
				U(s, e, n);
				continue;
			}
			if (u === "attributename" && kt(f, "href")) {
				U(s, e, n);
				continue;
			}
			if (!i.forceKeepAttr) {
				if (!i.keepAttr) {
					U(s, e, n);
					continue;
				}
				if (!Pe && K(fn, f)) {
					U(s, e, n);
					continue;
				}
				if (D && (f = G(f)), !On(o, u, f)) {
					U(s, e, n);
					continue;
				}
				f = jn(o, u, c, f), f !== d && Mn(e, s, c, f) && p && Ct(t.removed);
			}
		}
		$(S.afterSanitizeAttributes, e, null), En(e, n);
	}, Pn = function(e) {
		let t = null, n = It(e);
		for ($(S.beforeSanitizeShadowDOM, e, null); t = n.nextNode();) if ($(S.uponSanitizeShadowNode, t, null), Dn(t, e), Nn(t, e), Rt(t.content) && Pn(t.content), v(t) === Q.element) {
			let e = ne(t);
			Rt(e) && (Fn(e), Pn(e));
		}
		$(S.afterSanitizeShadowDOM, e, null);
	}, Fn = function(e) {
		let t = [{
			node: e,
			shadow: null
		}];
		for (; t.length > 0;) {
			let e = t.pop();
			if (e.shadow) {
				Pn(e.shadow);
				continue;
			}
			let n = e.node, r = v(n) === Q.element, i = te(n);
			if (i) for (let e = i.length - 1; e >= 0; --e) t.push({
				node: i[e],
				shadow: null
			});
			if (r) {
				let e = ie ? ie(n) : null;
				if (typeof e == "string" && z(e) === "template") {
					let e = n.content;
					Rt(e) && t.push({
						node: e,
						shadow: null
					});
				}
			}
			if (r) {
				let e = ne(n);
				Rt(e) && t.push({
					node: null,
					shadow: e
				}, {
					node: e,
					shadow: null
				});
			}
		}
	};
	return t.sanitize = function(e) {
		let n = arguments.length > 1 && arguments[1] !== void 0 ? arguments[1] : {}, i = null, a = null, o = null, s = null;
		if ($e = !e, $e && (e = "<!-->"), typeof e != "string" && !pn(e) && (e = zt(e), typeof e != "string")) throw q("dirty is not a string, aborting");
		if (!t.isSupported) return e;
		Ie ? (C = Le, w = Re) : ct(n), (S.uponSanitizeElement.length > 0 || S.uponSanitizeAttribute.length > 0) && (C = X(C)), S.uponSanitizeAttribute.length > 0 && (w = X(w)), t.removed = [];
		let c = A && typeof e != "string" && pn(e);
		if (c) {
			Pt(e);
			let t = ae(e);
			if (typeof t == "string") {
				let n = z(t);
				if (!C[n] || ke[n]) throw _t(e), q("root node is forbidden and cannot be sanitized in-place");
			}
			if (Lt(e)) throw _t(e), q("root node is clobbered and cannot be sanitized in-place");
			try {
				Fn(e);
			} catch (t) {
				throw _t(e), t;
			}
		} else if (pn(e)) i = Ft("<!---->"), a = i.ownerDocument.importNode(e, !0), a.nodeType === Q.element && a.nodeName === "BODY" || a.nodeName === "HTML" ? i = a : i.appendChild(a), Fn(i);
		else {
			if (!k && !D && !O && e.indexOf("<") === -1) return y && Ve ? ue(e) : e;
			if (i = Ft(e), !i) return k ? null : Ve ? b : "";
		}
		i && ze && B(i.firstChild);
		let l = c ? e : i;
		try {
			let e = It(l);
			for (; o = e.nextNode();) Dn(o, l), Nn(o, l), Rt(o.content) && Pn(o.content);
		} catch (n) {
			throw c && (_t(e), xt(t.removed, (e) => {
				e.element && bt(e.element);
			})), n;
		}
		if (c) {
			let n = !1;
			if (xt(t.removed, (t) => {
				t.element && (t.element === e && (n = !0), bt(t.element));
			}), n) throw q("a node selected for removal could not be safely returned; refusing to sanitize in place");
			return D && J(e), e;
		}
		if (k) {
			if (D && J(i), Be) for (s = he.call(i.ownerDocument); i.firstChild;) s.appendChild(i.firstChild);
			else s = i;
			return (w.shadowroot || w.shadowrootmode) && (s = _e.call(r, s, !0)), s;
		}
		let u = O ? i.outerHTML : i.innerHTML;
		return O && C["!doctype"] && i.ownerDocument && i.ownerDocument.doctype && i.ownerDocument.doctype.name && K(sn, i.ownerDocument.doctype.name) && (u = "<!DOCTYPE " + i.ownerDocument.doctype.name + ">\n" + u), D && (u = G(u)), y && Ve ? ue(u) : u;
	}, t.setConfig = function() {
		let e = arguments.length > 0 && arguments[0] !== void 0 ? arguments[0] : {};
		ct(e), Ie = !0, Le = C, Re = w;
	}, t.clearConfig = function() {
		at = null, Ie = !1, Le = null, Re = null, y = oe, b = "";
	}, t.isValidAttribute = function(e, t, n) {
		at || ct({});
		let r = z(e), i = z(t);
		return On(r, i, n);
	}, t.addHook = function(e, t) {
		typeof t == "function" && W(S, e) && wt(S[e], t);
	}, t.removeHook = function(e, t) {
		if (W(S, e)) {
			if (t !== void 0) {
				let n = St(S[e], t);
				return n === -1 ? void 0 : Tt(S[e], n, 1)[0];
			}
			return Ct(S[e]);
		}
	}, t.removeHooks = function(e) {
		W(S, e) && (S[e] = []);
	}, t.removeAllHooks = function() {
		S = vn();
	}, t;
}
var $ = xn(), Sn = /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i, Cn = !1;
function wn(e) {
	Cn ||= ($.addHook("afterSanitizeAttributes", (e) => {
		e.tagName === "A" && e.hasAttribute("href") && (e.setAttribute("target", "_blank"), e.setAttribute("rel", "noopener noreferrer"));
	}), !0);
	let { fields: t, body: n } = Tn(e), r = (t ? On(t) : "") + z.parse(n, {
		async: !1,
		gfm: !0
	});
	return $.sanitize(r, {
		ALLOWED_URI_REGEXP: Sn,
		FORBID_TAGS: [
			"style",
			"form",
			"input",
			"button",
			"textarea",
			"select",
			"iframe",
			"object",
			"embed"
		],
		FORBID_ATTR: ["style"]
	});
}
function Tn(e) {
	let t = /^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(e);
	if (!t) return {
		fields: null,
		body: e
	};
	let n = [];
	for (let r of t[1].split(/\r?\n/)) {
		if (!r.trim() || r.trim().startsWith("#")) continue;
		let t = /^\s+-\s+(.*)$/.exec(r), i = /^([A-Za-z0-9_][\w-]*)\s*:\s*(.*)$/.exec(r);
		if (t && n.length) n[n.length - 1][1].push(Dn(t[1]));
		else if (i) n.push([i[1], En(i[2])]);
		else return {
			fields: null,
			body: e
		};
	}
	return {
		fields: n,
		body: e.slice(t[0].length)
	};
}
function En(e) {
	let t = e.trim();
	if (!t) return [];
	let n = /^\[(.*)\]$/.exec(t);
	return n ? n[1].split(",").map((e) => Dn(e)).filter(Boolean) : [Dn(t)];
}
function Dn(e) {
	let t = e.trim();
	return /^(["']).*\1$/.test(t) ? t.slice(1, -1) : t;
}
function On(e) {
	return `<dl class="front-matter">${e.map(([e, t]) => {
		let n = t.length ? t.map((e) => `<dd>${z.parseInline(e, {
			async: !1,
			gfm: !0
		})}</dd>`).join("") : "<dd></dd>";
		return `<div><dt>${kn(e)}</dt>${n}</div>`;
	}).join("")}</dl>`;
}
function kn(e) {
	return e.replace(/[&<>"']/g, (e) => ({
		"&": "&amp;",
		"<": "&lt;",
		">": "&gt;",
		"\"": "&quot;",
		"'": "&#39;"
	})[e]);
}
//#endregion
//#region src/doc-view/doc-view.ts
var An = import.meta.url.replace(/doc-view\.js(?:\?.*)?$/, "doc-view.css"), jn = /^\/\.(?:oidc|account|well-known)\//;
async function Mn() {
	let e = document.querySelector("main");
	if (!e || jn.test(location.pathname) || !/\.md$/i.test(location.pathname)) return;
	let t = await fetch(location.href, {
		headers: { Accept: "text/markdown" },
		credentials: "include"
	});
	if (!t.ok || !(t.headers.get("content-type") ?? "").startsWith("text/markdown")) return;
	await Nn(), e.innerHTML = `<article class="prose">${wn(await t.text())}</article>`, document.body.classList.add("doc-view");
	let n = e.querySelector("h1");
	n?.textContent && (document.title = n.textContent);
}
function Nn() {
	return new Promise((e, t) => {
		let n = Object.assign(document.createElement("link"), {
			rel: "stylesheet",
			href: An
		});
		n.onload = () => e(), n.onerror = () => t(/* @__PURE__ */ Error("doc-view.css did not load")), document.head.append(n);
	});
}
Mn().catch(() => {});
//#endregion
