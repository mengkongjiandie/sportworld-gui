# 第三方组件与许可声明 / Third-Party Notices

本项目在源码与发布包中使用了以下第三方组件。分发时请完整保留本文件。

This project bundles or depends on the third-party components listed below.
Keep this file intact when redistributing.

---

## 1. 协议层代码 / Protocol layer

**来源 / Source:** [Inverx/com.zjwh.android_wh_physicalfitness](https://github.com/Inverx/com.zjwh.android_wh_physicalfitness)
**许可 / License:** MIT
**说明:** 位于 `com.zjwh.android_wh_physicalfitness/` 目录。协议逆向、加密还原、轨迹合成等核心实现均来自该项目，本项目仅做图形界面封装与少量适配补丁（源文件中以 `[PATCH]` 标注）。

**注意:** 上游 README 中含「禁止商用」等补充条款。本项目的 MIT 许可仅覆盖本项目自身新增的代码；上游代码的使用请遵循上游授权条款。如有疑问请与上游作者确认。

---

## 2. Node.js

**来源 / Source:** [nodejs/node](https://github.com/nodejs/node)
**许可 / License:** MIT
**分发形式:** 发布包内 `node/node.exe`

Copyright (c) Node.js contributors. All rights reserved.

完整许可文本见 https://github.com/nodejs/node/blob/main/LICENSE

---

## 3. Playwright

**来源 / Source:** [microsoft/playwright](https://github.com/microsoft/playwright)
**许可 / License:** Apache-2.0
**分发形式:** 发布包内 `node/node_modules/playwright`

完整许可文本见 https://github.com/microsoft/playwright/blob/main/LICENSE

---

## 4. 极验（Geetest）前端资源

**来源 / Source:** 极验验证服务（geetest.com）在运行时下发的静态资源
**分发形式:** 位于 `com.zjwh.android_wh_physicalfitness/协议/7.3.92/login/` 目录

**声明:** 这些资源由第三方验证服务提供，本项目**未获得明确的再分发授权**。它们仅用于与该校平台既有的验证流程对接。如果你要基于本仓库做公开分发，建议：

- 从发布包中移除这些静态资源，改为运行时按需获取；或
- 直接向上游项目维护者 / 极验确认再分发的许可范围。

---

## 5. Python 运行时

**来源 / Source:** [python/cpython](https://github.com/python/cpython)
**许可 / License:** PSF License
**分发形式:** 发布包内 `_internal/`（由 PyInstaller 打包）

---

## 6. 其他

- PyInstaller（GPL-2.0 with bootloader exception）
- tkinter / Tcl / Tk（Tcl/Tk License）

---

## 本项目自身许可 / This project's license

MIT，见根目录 `LICENSE`。

MIT 许可仅授予本项目作者创作的代码（GUI 层、打包脚本、协议适配补丁）。它**不能**也不试图改变上述任何第三方组件原有的授权条件。