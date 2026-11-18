# -*- coding: utf-8 -*-
"""运动世界校园 登录助手（密码走 getpass，不进命令行历史）"""
import sys, os, json, getpass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from login import LoginClient

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_session.json")

def main():
    st = {}
    if os.path.exists(STATE):
        try:
            st = json.load(open(STATE, encoding="utf-8"))
        except Exception:
            st = {}
    phone = st.get("phone") or input("手机号: ").strip()
    if not phone:
        print("未输入手机号"); return 1
    pwd = getpass.getpass("密码（输入时不显示）: ")
    if not pwd:
        print("未输入密码"); return 1

    print("\n[*] 开始登录（自动破极验 v4 滑块，20~60 秒）...\n")
    client = LoginClient()
    try:
        result = client.login(phone, pwd, progress_callback=lambda m: print("    [进度] " + str(m)))
    except TypeError:
        result = client.login(phone, pwd)
    except Exception as e:
        print("\n[!] 异常: %s: %s" % (type(e).__name__, e)); return 1

    print("")
    if not getattr(result, "success", False):
        print("[!] 登录失败: [%s] %s" % (getattr(result, "error_code", "?"), getattr(result, "message", "")))
        return 1
    u = getattr(result, "user", None)
    if u is None:
        print("[!] 无 user 对象"); return 1

    info = {
        "phone": phone,
        "name": getattr(u, "name", ""),
        "campus_id": getattr(u, "campus_id", ""),
        "campus_name": getattr(u, "campus_name", ""),
        "token": getattr(u, "token", ""),
        "uid": getattr(u, "uid", ""),
        "unid": getattr(u, "unid", ""),
    }
    json.dump(info, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=" * 56)
    print("  登录成功")
    print("=" * 56)
    print("  姓名 : %s" % info["name"])
    print("  学号 : %s" % info["campus_id"])
    print("  学校 : %s" % info["campus_name"])
    print("  UID  : %s   UNID : %s" % (info["uid"], info["unid"]))
    print("=" * 56)
    print("  已保存 _session.json（用完记得删）")
    return 0

if __name__ == "__main__":
    sys.exit(main())