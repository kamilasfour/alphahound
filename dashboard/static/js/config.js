/* ══ CONFIG ══ */
const API = '';

const VIEWS   = ['checkin','convergence','portfolio','tradelog','sectors','universe','global','macro','congress','options','health','earnings','alerts','map'];
const R_TABS  = [];

const UNIVERSE_CATS = {
  'US Stocks':    ['AAPL','NVDA','TSLA','AMD','AMZN','MSFT','META','GOOG','GOOGL','ARM','AVGO','NOW','QCOM','NFLX','PLTR','GME','AMC','MSTR','COIN','HOOD','RBLX','SNAP','SHOP','SQ','UBER','LYFT','INTC','SMCI','SNDK','BAC','JPM','GS','MS','V','MA','SOFI','LLY','UNH','PFE','MRK','ABBV','JNJ','COST','WMT','TGT','XOM','CVX','F','BE'],
  'Broad ETFs':   ['SPY','QQQ','IWM','DIA','VTI'],
  'Sectors':      ['XLK','XLF','XLE','XLV','XLI','XLB','XLU','XLRE','XLC','XLY','XLP'],
  'Thematic':     ['SMH','SOXX','XBI','IBB','ARKK','KWEB','FINX','GDX','OIH'],
  'Commodities':  ['GLD','IAU','SLV','USO','UNG','WEAT','CORN','PDBC','DJP'],
  'International':['EEM','EWJ','FXI','EWZ','EWG','EWU','EWY','INDA','MCHI'],
  'Macro':        ['TLT','HYG','LQD','UUP','UVXY','SVXY'],
};

const INTL_LABELS = {
  EEM:'Emerging Mkts', EWJ:'Japan', FXI:'China', EWZ:'Brazil',
  EWG:'Germany', EWU:'UK', EWY:'S.Korea', INDA:'India', MCHI:'MSCI China',
  TLT:'20yr Treasuries', HYG:'High Yield', LQD:'Corp Bonds',
  UUP:'US Dollar', UVXY:'VIX Long', SVXY:'VIX Short',
};

const TYPE_LABELS = {
  news_vs_institutional:'News vs Inst',
  congress:'Congress',
  options_led:'Options-led',
  confirmed:'Confirmed',
  retail_vs_institutional:'Retail vs Inst',
  multi_source:'Multi-source',
};

const ROLE_LABELS = {
  UVXY:'VIX / vol', TLT:'20yr Treasury', UUP:'US Dollar',
  HYG:'High Yield', LQD:'Corp Bonds', EWJ:'Japan', FXI:'China',
  EWG:'Germany', EEM:'Emerging Mkts', SPY:'US Market',
  QQQ:'US Tech', IWM:'Small Caps', GLD:'Gold', USO:'Crude Oil',
};
