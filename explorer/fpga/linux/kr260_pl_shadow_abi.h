#ifndef KR260_PL_SHADOW_ABI_H
#define KR260_PL_SHADOW_ABI_H
#include <stdint.h>
#include <stddef.h>
/* Storage fields below are LITTLE ENDIAN. Use cpu_to_leXX/leXX_to_cpu in kernel.
 * Do not cast this structure onto MMIO; use readl/writel under a driver mutex. */
#define KPL_MAGIC UINT32_C(0x4b504c31)
#define KPL_ABI UINT32_C(0x00010000)
#define KPL_BUILD UINT32_C(0x26110201)
#define KPL_BASE UINT32_C(0x80300000)
#define KPL_SIZE UINT32_C(0x10000)
#define KPL_SNAPSHOT_REQ 0x020
#define KPL_SNAPSHOT_ACK 0x024
#define KPL_MODE 0x030
#define KPL_STATUS 0x034
#define KPL_EPOCH 0x03c
#define KPL_RESULT 0x070
#define KPL_EVENT_MASK 0x078
#define KPL_EVENT_HEAD 0x800
#define KPL_EVENT_COUNT 0x840
#define KPL_EVENT_POP 0x844
#define KPL_STAGING 0x1000
#define KPL_COMMIT 0x1080
#define KPL_COMMIT_KEY UINT32_C(0x53484457)
#define KPL_EVENT_SHADOW_FRAME 0x0210
#define KPL_EVENT_CAN_SOF 0x0401
#define KPL_EVENT_CAN_EOF_SAMPLE 0x0402
struct __attribute__((packed)) kpl_cmd_v1 {
 uint32_t magic; uint16_t schema,length; uint32_t epoch,seq;
 uint64_t trace_id,apply_cycle,expire_cycle;
 uint8_t channel,kind; uint16_t flags;
 int32_t joints_mdeg[6]; int32_t gripper_um; int16_t torque_mnm;
 uint16_t unit_profile,coordinate_profile,reserved0;
 uint64_t ps_mono_ns; uint32_t transform_revision,crc32c; uint8_t reserved[32];
};
struct __attribute__((packed)) kpl_event_v1 {
 uint16_t schema,length; uint32_t flags,build,boot_cookie;
 uint16_t domain,channel,kind,reserved0; uint32_t seq,aux;
 uint64_t trace_id,cycle; uint16_t payload_len,reserved1;
 uint8_t data[8]; uint32_t reserved2;
};
#if defined(__cplusplus)
static_assert(sizeof(kpl_cmd_v1)==128,"command size");
static_assert(sizeof(kpl_event_v1)==64,"event size");
static_assert(offsetof(kpl_cmd_v1,crc32c)==92,"CRC offset");
static_assert(offsetof(kpl_event_v1,data)==52,"data offset");
#else
_Static_assert(sizeof(struct kpl_cmd_v1)==128,"command size");
_Static_assert(sizeof(struct kpl_event_v1)==64,"event size");
_Static_assert(offsetof(struct kpl_cmd_v1,crc32c)==92,"CRC offset");
_Static_assert(offsetof(struct kpl_event_v1,data)==52,"data offset");
#endif
#endif
