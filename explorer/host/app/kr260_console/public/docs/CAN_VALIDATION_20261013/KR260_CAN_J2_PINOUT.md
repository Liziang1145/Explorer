# KR260 当前修复版固件 CAN 排针映射

核对日期：2026-10-13。适用于当前 kr260_reset_fix 固件，不是 KR260 出厂默认 CAN 功能。

## 找到 J2 / Pmod1

从元件面看板卡，摆放成网口、USB、DisplayPort、电源接口朝下：上边缘有四组 2×6 Pmod 排针，**J2／Pmod1 是最右边、靠近右上角安装孔的那一组**。靠近 SFP 金属笼的最左一组不是 J2。

位置更正：此前把 UG1092 中四个接口的合并标签误当成从左到右的排列顺序，写成 J2 在最左边。AMD 官方 GPS 示例的实物接线图明确显示 Pmod1 在最右边。CAN 信号与 J2 脚号映射不受这次位置更正影响。

下面是 AMD 官方 UG1092 中的板卡布局图。图中“J2、J18、J19、J20”是四组 Pmod 的合并标签，不能把文字顺序当作实物排列顺序。

![AMD 官方 KR260 板卡布局图：四组 Pmod 位于板卡上边缘](./kr260-official-top.png)

图片来源：[AMD UG1092 — Interfaces，Figure 1：Interfaces and Connectors—Top of Card](https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Interfaces)。图片使用本地文件，Markdown 预览时不依赖外网。

## 官方 J2 实物接线图

这张 AMD 官方 GPS 示例图将外设接在 Master KR260 的 **最右侧 Pmod1／J2**。右下角放大图显示偶数排接线；官方接线表注明 IO6=J2-4、IO7=J2-6、IO8=J2-8、GND=J2-10、3.3V=J2-12。它用于确认接口位置和脚号，GPS 功能不适用于当前 CAN 固件。

![AMD 官方 Pmod1／J2 实物接线图，右下角有接口放大图](./kr260-official-gps-j2-wiring.png)

来源：[AMD 官方 GPS 示例 — Board Setup and Application Deployment](https://xilinx.github.io/kria-apps-docs/kr260/build/html/docs/gps_1588_ptp/src/app_deployment.html)。

## J2 线序原理图与针脚对照图

### 已核对的官方原理图：第 10 页

已打开你下载的 XTP743 原理图：**PDF 第 10 页（共 25 页），标题 `10 - PMOD1&2`，右上角的连接器 `J2`**。文件图号为 `038-05101-01`，版本 `A02`，图纸日期为 2021-10-15。

[打开官方原理图 PDF](../xtp743-kr260-schematic/038-05101-01_sck-kr_reva02_SKIT_20211015.pdf#page=10)。如果编辑器没有跳转到指定页，请手动输入第 10 页。

以下图片直接从这份官方 PDF 第 10 页渲染、截取，未修改信号或脚号：

![XTP743 官方原理图第 10 页右上角 J2 完整针脚定义](./kr260-j2-official-schematic.png)

完整第 10 页，便于查看上下文及右下角的页码、图号和版本：

![XTP743 官方原理图第 10 页：10 - PMOD1&2](./official-schematic-page-10.png)

| J2 物理脚号 | 官方原理图网络名称 | 当前固件用途 |
|---|---|---|
| 1 | PMOD1_IO1_HDA11 | CAN0 TX |
| 2 | PMOD1_IO5_HDA15 | CTU CAN2 TX |
| 3 | PMOD1_IO2_HDA12 | CAN0 RX |
| 4 | PMOD1_IO6_HDA16_CC | CTU CAN2 RX |
| 5 | PMOD1_IO3_HDA13 | CAN1 TX |
| 6 | PMOD1_IO7_HDA17 | 未分配给 CAN |
| 7 | PMOD1_IO4_HDA14 | CAN1 RX |
| 8 | PMOD1_IO8_HDA18 | 未分配给 CAN |
| 9、10 | GND | 共地 |
| 11、12 | PMOD_3V3 | 3.3V 电源 |

官方原理图定义的是排针网络；表中的 CAN 用途来自当前固件 XDC，不是原理图自带的 CAN 功能。原理图的连接器符号不是实物正面视图。

### 公开文章中的辅助图

下图为公开技术文章中展示的 KR260 J2 原理图截图，明确列出 1～12 脚及各个网络名称。原理图符号的上下左右不代表插孔正面方向。

![KR260 J2 原理图截图：奇数脚 IO1～IO4，偶数脚 IO5～IO8，9／10 地，11／12 为 3.3V](./kr260-j2-schematic-reference.png)

同一原作者还提供了带实物方向标注的针脚对照图：Pmod1 左端标出 1／2，右端标出 11／12。

![KR260 Pmod 物理脚号、FPGA 封装脚与实物端点方向对照图](./kr260-pmod-physical-pinout-reference.png)

以上两图来源：[Whitney Knitter — RPi+PMOD Connector GPIO with Custom PL Design in Kria KR260](https://www.hackster.io/whitney-knitter/rpi-pmod-connector-gpio-with-custom-pl-design-in-kria-kr260-53c40e)。这是原作者的技术文章，区别于上面的 AMD 官方示例图；针脚表已与当前 XDC 和 AMD 官方接线表交叉核对。

### 从插孔正面看时的排列

板卡元件面朝上，从板外正对 J2 插孔、朝板内看。按官方示例的下排为偶数排，以及实物端点标注换算，排列如下（文字图为本文整理，不是官方原图）：

```text
                从板外正对 J2 插孔看
             电源端                         信号起始端
上排： 11 3V3   9 GND   7 CAN1_RX   5 CAN1_TX   3 CAN0_RX   1 CAN0_TX
下排： 12 3V3  10 GND   8 未使用    6 未使用    4 CAN2_RX   2 CAN2_TX
```

从板内向外看，左右会镜像。接线时以实物 1 脚标记为准，不把原理图符号当作插孔正面图。

## 信号映射

| Linux 接口 | 控制器 | J2 TX 物理脚 | J2 RX 物理脚 | FPGA TX / RX 封装脚 |
|---|---|---|---|---|
| fpga_can0 | PS CAN0 | 1 | 3 | H12 / E10 |
| fpga_can1 | PS CAN1 | 5 | 7 | D10 / C11 |
| fpga_can2 | PL CTU CAN | 2 | 4 | B10 / E12 |

J2 9、10 脚为 GND；11、12 脚为 3.3 V；6、8 脚没有分配给这三路 CAN。

以下是以 1 脚为起点的逻辑针位示意，不表示板卡照片上的绝对上下左右；实物需先确认 1 脚标记，不能从任意一端开始数：

```text
1 CAN0_TX   3 CAN0_RX   5 CAN1_TX   7 CAN1_RX   9 GND   11 3V3
2 CAN2_TX   4 CAN2_RX   6 未使用    8 未使用   10 GND   12 3V3
```

KR260 的 J2 物理编号和某些 Pmod 模块采用的两行 1–6 / 7–12 编号不同。也不要将 BoardStore 的 pmod1_pin1..8 信号索引直接当作 J2 物理脚号。

这些是 LVCMOS33 TX/RX 逻辑信号。接总线时，FPGA TX 接外部 CAN 收发器 TXD，收发器 RXD 接 FPGA RX，共地；USB-CAN 的 CANH/CANL 接收发器 CANH/CANL，不能直接接这些 FPGA IO。

## 核对依据

- AMD UG1092 Interfaces（J2 位置及 Pmod 接口）：https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Interfaces
- AMD 官方 GPS 示例接线表（J2 偶数排物理编号，IO6=4、IO7=6、IO8=8、GND=10、3V3=12）：https://xilinx.github.io/kria-apps-docs/kr260/build/html/docs/gps_1588_ptp/src/app_deployment.html
- AMD BoardStore 载板与 SOM IO 映射：https://github.com/Xilinx/XilinxBoardStore/blob/2022.2/boards/Xilinx/kr260_carrier/1.0/board.xml
- 当前交付 XDC：../KR260_RESET_FIX_20261013_BIT_DOCS/KR260_RESET_FIX_20261013/kr260_can_pins.xdc
- KR260 上游工程物理针号交叉核对：https://git.byronlathi.com/bslathi19/taxi/commit/d5ed74431ae77d6275d014c75d9ba3cc035a5d51?files=example%2FKR260%2Ffpga

完整官方原理图下载入口：[AMD XTP743 — KR260 Carrier Card Schematic](https://account.amd.com/en/forms/downloads/license-form-tip.html?cid=bad0ada6-9a32-427e-a793-c68fed567427&filename=xtp743-kr260-schematic.zip&license=eula-design-license)。你已下载并解压至 `xtp743-kr260-schematic`；本次已直接检查其中 PDF 的第 10 页，确认 J2 完整针脚定义。其余页面没有逐页审阅。
