import argparse
import getpass
import json
import sys
import warnings

from .task_agent import TaskAgent
from .client import AgentError, JevClient
from .config import load
from .tools import Tools
from .safety import display_command
from .speech import Speech, voice_loop
from .shortcuts import hold_to_talk
from . import credentials
from .laya_client import LayaClient

PROVIDERS = (*JevClient.PROVIDERS, 'laya')


def make_client(provider, timeout=15, model=None,device='cpu',threshold=.65):
    return LayaClient(timeout,device,threshold) if provider == 'laya' else JevClient(model,timeout,provider=provider)


def read_key(provider="typesafe"):
    # Refuse getpass's echoed fallback when a terminal is unavailable.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        label = {"openrouter":"OpenRouter","typesafe":"Typesafe","opencode":"OpenCode Zen"}[provider]
        return getpass.getpass(f"{label} API anahtarı (gizli): ").strip()


def check_connection(client):
    """A real typed API request, independent of speech and desktop adapters."""
    try:
        answers=client.evaluate('This is a connection test.',{'connection':{
            'type':'noul','instructions':'Does the text explicitly say this is a connection test?'}})
        answer=answers.get('connection')
        if not isinstance(answer,dict) or answer.get('type')!='noul':
            raise AgentError('INVALID_RESPONSE')
        probability=TaskAgent.probability(answer.get('noul'))
        return {'success':True,'api_response_valid':True,'provider':client.provider,
                'model':client.model,'probability':probability,'desktop_action_executed':False,
                **({'device':client.device} if client.provider=='laya' else {})}
    except AgentError as error:
        return {'success':False,'error':error.code,'desktop_action_executed':False,
                **({'reason':error.reason} if error.reason else {})}


def show_event(event, data):
    if event == "evaluating":
        print("  Model: komut çözümleniyor…", flush=True)
    elif event == "selected":
        target=data.get('application') or data.get('action')
        if data.get('source') == 'configured_command':
            print(f"  Seçim: {target} · yapılandırılmış komut, Jev çağrısı gerekmedi",flush=True)
        else:
            print(f"  Seçim: {target} · güven {data['confidence']:.1%}", flush=True)
    elif event == "executing":
        print("  Eylem: " + json.dumps(data, ensure_ascii=False), flush=True)
    elif event == "observing":
        print(f"  Gözlem {data['step']}: {data['source']} · {data['targets']} hedef · {data.get('application','unknown')}", flush=True)
    elif event == 'shortlist':
        print(f"  Laya hedef süzme: {data['question']} · {data['original']} → {data['kept']} seçenek; güven bu listeye aittir.",flush=True)
    elif event == "result":
        print("  Eylem sonucu: " + json.dumps(data, ensure_ascii=False), flush=True)
    elif event == "retry":
        print("  Yeniden gözlem: " + data['error'], flush=True)
    elif event == "uncertain":
        print(f"  Karar reddedildi: {data['question']} → {data['choice']} · "
              f"güven {data['confidence']:.1%} (eşik {data['confidence_threshold']:.0%}) · "
              f"olasılık {data['probability']:.1%} (eşik {data['probability_threshold']:.0%})", flush=True)


def confirm_action(action):
    print("Onay gerekiyor: " + json.dumps(action, ensure_ascii=False))
    try:
        return input("Uygulamak için evet yaz: ").strip().lower() == "evet"
    except (EOFError, KeyboardInterrupt):
        return False


def show_result(agent, command):
    print("  Komut: " + json.dumps(display_command(command), ensure_ascii=False))
    result = agent.process(command, on_event=show_event, confirm=confirm_action)
    if result.get('success') and result.get('commands'):
        print(result['commands'])
    elif result.get("success") and result.get("action") == "task_complete":
        print(f"  Sonuç: {result['steps']} eylem uygulandı; Jev döngüyü bitirdi. Görev sonucunu ekrandan kontrol edin.")
    elif result.get("success") and result.get("verified") and result.get('application'):
        print(f"  Sonuç: {result['application']} penceresi doğrulandı.")
    elif result.get('success') and result.get('action')=='navigate' and result.get('verified'):
        print(f"  Sonuç: {result['destination_host']} adresine gezinme doğrulandı.")
    elif result.get("success"):
        print("  Sonuç: " + json.dumps(result, ensure_ascii=False))
    else:
        print("  Hata: " + result.get("error", "EXECUTION_FAILED"))
        if result.get("error") == "APP_NOT_CONFIGURED":
            print("  Yapılandırılmış uygulamalar: " + ", ".join(agent.apps))
        if result.get('error') == 'PROVIDER_MODEL_MISMATCH':
            print("  jev-1.13-free için --provider opencode ve ayrı OpenCode Zen anahtarı gerekir.\n"
                  "  OpenRouter anahtarı OpenCode'a gönderilmedi; ücretli modele geçilmedi.")
        if result.get("error") == 'ACCESS_DENIED':
            print('  Erişim nedeni: ' + result.get('reason','ACCESS_POLICY_UNKNOWN'))
            print('  403 tek başına anahtarın yanlış olduğunu göstermez; /check ile bağlantıyı sınayın.')
        if result.get("error") == "AUTHENTICATION_FAILED":
            print("  /key ile anahtarı değiştirebilirsin.")
        if result.get('error') in ('LAYA_TOO_MANY_TARGETS','LAYA_CONTEXT_LIMIT','LAYA_OPTION_LIMIT'):
            print('  Yerel modelin hedef/metin sınırı aşıldı. Daha dar bir ekran veya kısa komut kullanın.')
        if result.get('error')=='REPEATED_ACTION_BLOCKED':
            print('  Aynı eylemin tekrarı engellendi; uygulanmış adım yeniden çalıştırılmadı.')
    return result


def interactive(agent, provider=None, speech=None, listen_mode="hold", start_listening=False,device=None):
    if not sys.stdin.isatty():
        print("Etkileşimli kullanım için bir terminalde ./desktop-agent çalıştırın.")
        return 1
    print("Jev masaüstü ajanı · sürüm 2026-09-29.12\n"
          "Doğrulanan anahtar KDE güvenli anahtar kasasında hatırlanır.\n"
          "Belirli uygulama/site/arama komutları doğrudan; genel görevler Jev ile uygulanır.\n"
          "Örnek: Open Firefox · /check · /listen · /tools · /windows · /key · /help · /quit\n"
          "Laya yerelde; Jev seçildiğinde genel görevler seçilen API üzerinden çalışır.")
    try:
        if provider is None:
            while True:
                selected = input("Sağlayıcı: 3 OpenCode Zen Jev / 4 Laya İngilizce yerel / 1 OpenRouter / 2 Typesafe [3]: ").strip().lower()
                if selected in ("1", "openrouter"):
                    provider = "openrouter"
                    break
                if selected in ("2", "typesafe"):
                    provider = "typesafe"
                    break
                if selected in ('','3','opencode'):
                    provider = 'opencode'
                    break
                if selected in ('4','laya'):
                    provider='laya'
                    break
                print("1, 2, 3 veya 4 seçin.")
            agent.client = make_client(provider,agent.client.timeout)
        print(f"Sağlayıcı: {provider} · Model: {agent.client.model}")
        remembered=False
        if provider=='laya':
            if device is None:
                while True:
                    selected=input('Laya aygıtı: 1 CPU / 2 NVIDIA GPU [1]: ').strip().lower()
                    if selected in ('','1','cpu'):
                        device='cpu';break
                    if selected in ('2','gpu','cuda'):
                        device='cuda';break
                    print('1 veya 2 seçin.')
            agent.client.device=device
            print(f'İngilizce model yükleniyor · {device.upper()} · eşik {agent.client.threshold:.0%} · yerel…',flush=True)
        else:
            print(f"Komut metni {provider} API'ye gönderilecek.")
            agent.client.api_key = credentials.lookup(provider)
            remembered = bool(agent.client.api_key)
            if remembered:
                print('Anahtar güvenli kasadan alındı.')
            else:
                agent.client.api_key = read_key(provider)
            while not agent.client.api_key:
                print("Anahtar boş olamaz. Çıkmak için Ctrl+C.")
                agent.client.api_key = read_key(provider)
            print("Anahtar alındı.")
        connection_ok = True
        if provider in ('opencode','laya'):
            check = check_connection(agent.client)
            print(('  Yerel model testi: ' if provider=='laya' else '  API bağlantı testi: ')
                  + json.dumps(check,ensure_ascii=False),flush=True)
            connection_ok = check['success']
            if provider=='opencode' and connection_ok and not remembered:
                print('Anahtar güvenli kasaya kaydedildi.' if credentials.save(provider,agent.client.api_key)
                      else 'Anahtar kasasına kaydedilemedi; bu oturumda kullanılacak.')
            if not connection_ok and provider!='laya':
                print('Bağlantı doğrulanamadı. /check ile yeniden sınayın; anahtar reddedildiyse /key kullanın.')
            if not connection_ok and provider=='laya':
                print('Yerel model başlatılamadı. GPU kullanılamıyorsa oturumu CPU seçerek yeniden açın; otomatik indirme yapılmaz.')
        auto_listen = start_listening and connection_ok
        while True:
            command = "/listen" if auto_listen else input("\nSen > ").strip()
            auto_listen = False
            if not command:
                continue
            if command in ("/quit", "/exit"):
                break
            if command == "/help":
                print("İngilizce görev yazın veya /listen ile bas-konuş başlatın.\n"
                      "/tools: yetenekler · /windows: pencereler · /observe: güncel hedefler\n"
                      "/check: gerçek API bağlantısını sınar; masaüstü eylemi yapmaz\n"
                      "/panel: kontrol paneli · /features: yeni yetenekler · /history: geçmiş · /undo: geri al\n"
                      "/apps: uygulamalar · /key: anahtarı değiştir · /forget-key: kayıtlı anahtarı sil · /quit: çık")
                continue
            if command == '/check':
                print(('  Yerel model testi: ' if provider=='laya' else '  API bağlantı testi: ')
                      + json.dumps(check_connection(agent.client),ensure_ascii=False))
                continue
            if command == '/forget-key':
                if provider=='laya':
                    print('Laya yerel çalışır; kayıtlı API anahtarı yok.')
                    continue
                print('Kayıtlı anahtar silindi.' if credentials.forget(provider) else 'Anahtar kasası işlemi tamamlanamadı.')
                continue
            if command == "/tools":
                from .features import HELP
                print(HELP)
                print("Uygulama açma, pencere odaklama, URL/arama, güncel hedefe tıklama/yazma,\n"
                      "tarayıcı seçeneği seçme, tuş/kısayol, kaydırma. Terminal ve parola girişi engellenir.\n"
                      "Örnek: Search YouTube for Interstellar soundtrack\n"
                      "Örnek: Type 'hello world' in the Search field and click Search\n"
                      "Hedefler AT-SPI veya görev Firefox'unun DOM'undan okunur.")
                continue
            if command in ("/windows", "/observe"):
                try:
                    value = agent.desktop.desktop.windows() if command == "/windows" else agent.desktop.observe()
                    print(json.dumps(value, ensure_ascii=False, indent=2))
                except Exception:
                    print("Hata: OBSERVATION_FAILED")
                continue
            if command == "/listen" or command.startswith("/listen "):
                mode = command.split()[1] if len(command.split()) == 2 else listen_mode
                if mode not in ("hold", "ptt", "wake", "continuous"):
                    print("Modlar: hold, ptt, wake, continuous")
                    continue
                if speech is None:
                    print("Hata: SPEECH_NOT_CONFIGURED")
                    continue
                try:
                    if mode == "hold":
                        hold_to_talk(speech, lambda text: show_result(agent, text),
                                     speech.config.get("shortcut", "CTRL+ALT+v"), agent=agent)
                    else:
                        voice_loop(agent, speech, mode, lambda text: show_result(agent, text))
                except AgentError as error:
                    print("Hata: " + error.code)
                    if error.code in ("WHISPER_NOT_INSTALLED", "SPEECH_MODEL_MISSING"):
                        print("Whisper/model eksik. Otomatik indirme yapılmaz; metin girişi çalışmaya devam eder.")
                continue
            if command == "/apps":
                print("Uygulamalar: " + ", ".join(agent.apps))
                continue
            if command == "/key":
                if provider=='laya':
                    print('Laya API anahtarı gerektirmez.')
                    continue
                key = read_key(provider)
                if key:
                    agent.client.api_key = key
                    print("Anahtar değiştirildi; sonraki komutta doğrulanacak.")
                    if provider == 'opencode':
                        check=check_connection(agent.client)
                        print('  API bağlantı testi: ' + json.dumps(check,ensure_ascii=False),flush=True)
                        if check['success']:
                            print('Anahtar güvenli kasaya kaydedildi.' if credentials.save(provider,key)
                                  else 'Anahtar kasasına kaydedilemedi; bu oturumda kullanılacak.')
                else:
                    print("Boş giriş; önceki anahtar korunuyor.")
                continue
            if command.startswith(('/routine ', '/teach ', '/forget ')) or command in ('/routines','/aliases','/tabs','/targets','/history','/undo','/panel','/outputs','/stop','/features'):
                show_result(agent,command)
                continue
            if command.startswith("/"):
                print("Bilinmeyen CLI komutu. /help ile seçenekleri görün.")
                continue
            show_result(agent, command)
    except (EOFError, KeyboardInterrupt):
        print()
    except getpass.GetPassWarning:
        print("Gizli anahtar girişi kullanılamıyor; gerçek bir terminalde çalıştırın.")
        return 1
    finally:
        agent.client.api_key = None
        if isinstance(agent.client,LayaClient):
            agent.client.close()
        agent.desktop.close()
        features=getattr(agent,'features',None)
        if features:
            for widget in (features.overlay,features.panel):
                if widget: widget.close()
    print("Oturum kapandı.")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="desktop-agent")
    parser.add_argument("--provider", choices=PROVIDERS)
    parser.add_argument('--device',choices=('cpu','cuda'))
    commands = parser.add_subparsers(dest="mode")
    text = commands.add_parser("text")
    text.add_argument("command")
    text.add_argument("--dry-run", action="store_true")
    text.add_argument("--provider", choices=PROVIDERS, default=argparse.SUPPRESS)
    text.add_argument('--device',choices=('cpu','cuda'),default=argparse.SUPPRESS)
    commands.add_parser("apps")
    commands.add_parser("windows")
    commands.add_parser("observe")
    commands.add_parser("tools")
    terminal = commands.add_parser("interactive")
    terminal.add_argument("--provider", choices=PROVIDERS, default=argparse.SUPPRESS)
    terminal.add_argument('--device',choices=('cpu','cuda'),default=argparse.SUPPRESS)
    listen = commands.add_parser("listen")
    listen.add_argument("--provider", choices=PROVIDERS, default=argparse.SUPPRESS)
    listen.add_argument('--device',choices=('cpu','cuda'),default=argparse.SUPPRESS)
    listen.add_argument('--choose-provider',action='store_true',help='Başlangıçta Jev/Laya seçimini sor')
    listen.add_argument("--mode", dest="listening_mode", choices=("hold", "ptt", "wake", "continuous"), default="hold")
    commands.add_parser("speech-status")
    commands.add_parser("panel")
    args = parser.parse_args()
    try:
        apps = load("apps.json")
        config = load("config.json")
        if args.mode == "speech-status":
            try:
                binary, model = Speech(config.get("speech", {})).check()
                result = {"success": True, "binary": str(binary), "model": str(model)}
            except AgentError as error:
                result = {"success": False, "error": error.code, "downloaded": False}
        elif args.mode == "apps":
            result = {"success": True, "applications": list(apps)}
        elif args.mode in ("windows", "observe", "tools"):
            if args.mode == "tools":
                from .features import HELP
                result = {"success":True,"local_commands":HELP,"capabilities":["open_app","focus_window","navigate","click","type_text",
                                                        "select","press_key","scroll"],"model_generates_text":False}
            else:
                tools = Tools(apps,config["window_timeout"])
                try:
                    result = {"success":True,"observation":tools.desktop.windows() if args.mode=='windows' else tools.observe()}
                finally:
                    tools.close()
        else:
            provider = args.provider or config.get('provider','opencode')
            model = config["model"] if provider == "typesafe" else None
            agent = TaskAgent(make_client(provider,config["request_timeout"],model,args.device or 'cpu',config.get('laya',{}).get('threshold',.65)), apps,
                              Tools(apps, config["window_timeout"]), config, load("sites.json"))
            if args.mode in (None, "interactive", "listen", "panel"):
                choose_provider = getattr(args,'choose_provider',False) or (args.mode=='listen' and not args.provider)
                if args.mode=='panel':
                    import threading
                    from .features import Features
                    from .panel import show_panel
                    agent.cancel=threading.Event();agent.features=Features(agent)
                    if provider!='laya': agent.client.api_key=credentials.lookup(provider)
                    try: show_panel(agent,agent.features)
                    finally:
                        agent.client.api_key=None
                        if isinstance(agent.client,LayaClient): agent.client.close()
                        agent.desktop.close()
                    return 0
                return interactive(agent, None if choose_provider else provider, Speech(config.get("speech", {})),
                                   getattr(args, "listening_mode", "hold"),
                                   args.mode == "listen",args.device)
            try:
                result = agent.process(args.command, args.dry_run)
            finally:
                if isinstance(agent.client,LayaClient):
                    agent.client.close()
                agent.desktop.close()
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"success": False, "error": "INVALID_CONFIG"}))
        return 1
