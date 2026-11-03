#ifndef KR260_CAN_SWITCH_ABI_H
#define KR260_CAN_SWITCH_ABI_H
#include <stdint.h>
#include <stddef.h>
#define KCAN_MAGIC UINT32_C(0x4b434132)
#define KCAN_ABI UINT32_C(0x00020001)
#define KCAN_BUILD UINT32_C(0x26110303)
#define KCAN_BASE0 UINT32_C(0x80310000)
#define KCAN_BASE1 UINT32_C(0x80320000)
#define KCAN_NATIVE 0x4000
#define KCAN_SUBMIT 0x1080
#define KCAN_SUBMIT_KEY UINT32_C(0x41524d32)
#define KCAN_STATE 0x020
#define KCAN_GENERATION 0x024
#define KCAN_FAULTS 0x028
#define KCAN_OWNER_RESULT 0x02c
#define KCAN_TOKEN 0x030
#define KCAN_PREPARE 0x034
#define KCAN_CONFIRM 0x038
#define KCAN_COMMIT 0x03c
#define KCAN_HEARTBEAT 0x040
#define KCAN_FAULT_CLEAR 0x044
#define KCAN_AUTO_POLICY 0x048
#define KCAN_LEASE_MS 0x04c
#define KCAN_RETRY_MS 0x050
#define KCAN_RETRY_LIMIT 0x054
#define KCAN_RETRY_COUNT 0x058
#define KCAN_ACTION 0x05c
#define KCAN_FORCED_ISOLATIONS 0x064
#define KCAN_CORE_ID 0x068
#define KCAN_ERROR_COUNTERS 0x06c
#define KCAN_IRQ_STATUS 0x074
#define KCAN_IRQ_MASK 0x078
#define KCAN_IRQ_CLEAR 0x07c
#define KCAN_QUEUE_COUNT 0x080
#define KCAN_CMD_RESULT 0x084
#define KCAN_ENGINE_STATE 0x094
#define KCAN_FEEDBACK_VALID 0x098
#define KCAN_SNAPSHOT_SEQ 0x09c
#define KCAN_SNAPSHOT_REQ 0x0a0
#define KCAN_EVENT_STATE 0x0a4
#define KCAN_EVENT_POP 0x0a8
#define KCAN_EVENT_LOST 0x0ac
#define KCAN_DENIED_COUNT 0x0b0
#define KCAN_EVENT_MASK 0x0b4
#define KCAN_CONTROL_RESULT 0x0b8
#define KCAN_ENGINE_EVENT_LOST 0x0bc
#define KCAN_FAULT_ERRORS 0x0c0
#define KCAN_FAULT_TX_STATUS 0x0c4
#define KCAN_FAULT_CYCLE_LO 0x0c8
#define KCAN_FAULT_CYCLE_HI 0x0cc
#define KCAN_CAPS UINT32_C(0x000001ff)
#define KCAN_MODE_SHADOW 0x0d0
#define KCAN_ERR_STAT 0x0d4
#define KCAN_CORE_LIFECYCLE 0x0d8
#define KCAN_LIFECYCLE_TIMEOUT_MS 0x0dc
#define KCAN_CORE_OPERATIONAL (1u << 15)
#define KCAN_CORE_ENABLED (1u << 14)
#define KCAN_FAULT_CONFIG_TIMEOUT (1u << 6)
#define KCAN_FAULT_STOP_TIMEOUT (1u << 7)
#define KCAN_FAULT_START_TIMEOUT (1u << 8)
#define KCAN_FEEDBACK 0x100
#define KCAN_EVENT_HEAD 0x800
#define KCAN_STAGING 0x1000
enum kcan_owner { KCAN_PS=0, KCAN_GENERIC=1, KCAN_ARM=2, KCAN_ISOLATED=3 };
enum kcan_action { KCAN_NONE=0, KCAN_FALLBACK_PS=1, KCAN_RETRY_PL=2 };
/* All storage is little-endian; use readl/writel, never cast a pointer onto MMIO. */
struct __attribute__((packed)) kcan_cmd_v2 {
 uint32_t magic; uint16_t schema,length; uint32_t generation,seq;
 uint64_t trace_id,apply_cycle,expire_cycle;
 uint8_t channel,kind; uint16_t flags;
 int32_t joints_mdeg[6]; int32_t gripper_um; int16_t torque_mnm;
 uint16_t unit_profile,coordinate_profile,reserved0;
 uint64_t ps_mono_ns; uint32_t transform_revision,crc32c; uint8_t reserved[32];
};
struct __attribute__((packed)) kcan_event_v2 {
 uint16_t schema,length; uint32_t build,generation;
 uint16_t kind,channel; uint32_t seq,aux;
 uint64_t trace_id,cycle,wire_data; uint8_t reserved[16];
};
#if defined(__cplusplus)
static_assert(sizeof(kcan_cmd_v2)==128,"command size");
static_assert(offsetof(kcan_cmd_v2,crc32c)==92,"CRC offset");
static_assert(sizeof(kcan_event_v2)==64,"event size");
#else
_Static_assert(sizeof(struct kcan_cmd_v2)==128,"command size");
_Static_assert(offsetof(struct kcan_cmd_v2,crc32c)==92,"CRC offset");
_Static_assert(sizeof(struct kcan_event_v2)==64,"event size");
#endif
#endif
