# 第 6 章：系统属性

Android 的系统属性是一套设备级键值存储，是进程之间传递配置数据的主要机制。从 init 在早期启动阶段设置 `ro.build.fingerprint`，到 Java 应用读取 `persist.sys.language` 判断用户区域设置，系统属性贯穿 Android 栈的每一层。它们体积小（历史上 key 最多 32 字节，可变属性 value 最多 92 字节）、读取快（读取无需 IPC，只是共享内存查询），并且受控（写入由 init 通过 Unix domain socket 代理，并由 SELinux 强制执行）。

虽然系统属性表面上只是简单的键值接口，但其内部包含共享内存区域、trie 数据结构、SELinux 强制访问控制、protobuf 序列化持久化存储，以及构建期类型系统等多层协作。本章会沿着真实 AOSP 源码逐层拆解：从 `bionic/libc/system_properties/` 中的 bionic 实现，到 `system/core/init/property_service.cpp` 中的 property service，再到 `frameworks/base/core/java/android/os/SystemProperties.java` 中的 Java API，以及 Soong 构建系统里的 `sysprop_library` 模块类型。

---

## 6.1 属性架构

### 6.1.1 设计目标与约束

系统属性机制的架构来自几个明确约束：

1. **无锁读取。** 任意进程都必须能在不加锁、不执行 IPC 的情况下读取任意属性。这一点很关键，因为属性读取位于热路径上，例如每次 `getprop` 调用、Java 层读取构建特征、native daemon 检查 debug flag。

2. **单一写入者。** 只有 init 进程（PID 1）可以修改包含属性数据的共享内存区域。其他进程必须通过 Unix domain socket 向 init 发送请求。

3. **SELinux 强制执行。** 读取和写入都受 SELinux 控制。属性命名空间被划分到不同 SELinux context 中，进程必须具备对应的 `property_service { set }` 或 `file { read }` 权限。

4. **启动期不可变。** 以 `ro.` 开头的只读属性只能在启动期间设置一次，之后在设备生命周期内保持不可变。

5. **持久化。** 以 `persist.` 开头的属性会通过 protobuf 序列化文件写入 `/data/property/persistent_properties`，从而跨重启保留。

```mermaid
graph TB
    subgraph "用户空间进程"
        APP["Application<br/>(Java/Kotlin)"]
        NATIVE["Native Daemon<br/>(C/C++)"]
        SHELL["Shell<br/>(getprop/setprop)"]
    end

    subgraph "属性读取路径（无锁）"
        SHM["Shared Memory<br/>/dev/__properties__/*"]
    end

    subgraph "属性写入路径（IPC）"
        SOCK["Unix Domain Socket<br/>/dev/socket/property_service"]
        INIT["init (PID 1)<br/>PropertyService Thread"]
    end

    subgraph "存储"
        BUILDPROP["/system/build.prop<br/>/vendor/build.prop<br/>/product/etc/build.prop"]
        PERSIST["/data/property/<br/>persistent_properties"]
        KERNEL["Kernel cmdline<br/>androidboot.*"]
    end

    APP -->|"__system_property_find<br/>(mmap read)"| SHM
    NATIVE -->|"__system_property_find<br/>(mmap read)"| SHM
    SHELL -->|"__system_property_find<br/>(mmap read)"| SHM

    APP -->|"__system_property_set<br/>(socket write)"| SOCK
    NATIVE -->|"__system_property_set<br/>(socket write)"| SOCK
    SHELL -->|"__system_property_set<br/>(socket write)"| SOCK

    SOCK --> INIT
    INIT -->|"__system_property_update<br/>__system_property_add"| SHM
    INIT -->|"WritePersistentProperty"| PERSIST

    BUILDPROP -->|"PropertyLoadBootDefaults"| INIT
    KERNEL -->|"ProcessKernelCmdline"| INIT
    PERSIST -->|"LoadPersistentProperties"| INIT
```

### 6.1.2 共享内存区域

系统属性机制的基础是一组位于 `/dev/__properties__/` 下的内存映射文件。该目录位于 `tmpfs` 文件系统中，因此完全存在于内存里。init 会在启动早期创建该目录：

```cpp
// Source: system/core/init/property_service.cpp, PropertyInit()
void PropertyInit() {
    selinux_callback cb;
    cb.func_audit = PropertyAuditCallback;
    selinux_set_callback(SELINUX_CB_AUDIT, cb);

    mkdir("/dev/__properties__", S_IRWXU | S_IXGRP | S_IXOTH);
    CreateSerializedPropertyInfo();
    if (__system_property_area_init()) {
        LOG(FATAL) << "Failed to initialize property area";
    }
    if (!property_info_area.LoadDefaultPath()) {
        LOG(FATAL) << "Failed to load serialized property info file";
    }
    ...
}
```

`__system_property_area_init()` 由 bionic 实现，用于创建真正的内存映射文件。每个 SELinux context 在 `/dev/__properties__/` 下都有独立文件，此外还有一个全局 serial number 专用文件。

每个 property area 的大小定义在 `bionic/libc/system_properties/prop_area.cpp`：

```c
// Source: bionic/libc/system_properties/prop_area.cpp
#ifdef LARGE_SYSTEM_PROPERTY_NODE
constexpr size_t PA_SIZE = 1024 * 1024;       // 1 MB
#else
constexpr size_t PA_SIZE = 128 * 1024;        // 128 KB
#endif
constexpr uint32_t PROP_AREA_MAGIC = 0x504f5250;  // little-endian "PROP"
constexpr uint32_t PROP_AREA_VERSION = 0xfc6ed0ab;
```

init 以 `O_RDWR` 打开文件，并用 `PROT_READ | PROT_WRITE` 映射；其他进程则以只读方式打开同一文件，并用 `PROT_READ` 映射。`map_fd_ro()` 还会校验文件所有者与权限，只接受 root 拥有、组和其他用户不可写的文件，这保证了 property area 本身的可信性。

### 6.1.3 `prop_area` 结构

`prop_area` 是每个内存映射属性文件的头部结构，定义在 `bionic/libc/system_properties/include/system_properties/prop_area.h`：

```c
class prop_area {
 public:
    prop_area(const uint32_t magic, const uint32_t version)
        : magic_(magic), version_(version) {
        atomic_store_explicit(&serial_, 0u, memory_order_relaxed);
        memset(reserved_, 0, sizeof(reserved_));
        bytes_used_ = sizeof(prop_trie_node);
        bytes_used_ += __builtin_align_up(PROP_VALUE_MAX, sizeof(uint_least32_t));
    }

 private:
    uint32_t bytes_used_;
    atomic_uint_least32_t serial_;
    uint32_t magic_;
    uint32_t version_;
    uint32_t reserved_[28];
    char data_[0];
};
```

内存布局如下：

```text
+---------------------+  offset 0
|   bytes_used_ (4B)  |
+---------------------+  offset 4
|   serial_ (4B)      |  每次属性变化时原子递增
+---------------------+  offset 8
|   magic_ (4B)       |  0x504f5250 ("PROP")
+---------------------+  offset 12
|   version_ (4B)     |  0xfc6ed0ab
+---------------------+  offset 16
|   reserved_[28]     |  112 字节保留区
+---------------------+  offset 128
|   data_[]           |  Trie 节点、prop_info、value
+---------------------+  offset PA_SIZE
```

`serial_` 字段很关键。该区域内任意属性新增或修改时，它都会原子递增。读取者可以通过 `__system_property_area_serial()` 轮询该 serial，无需加锁即可检测属性变化。`data_[]` 区域以根 `prop_trie_node` 开始，后面是一个 `PROP_VALUE_MAX` 大小的 dirty backup area，再往后才是动态分配的 trie 节点和属性信息。

### 6.1.4 Trie 结构

属性使用混合 trie/二叉树结构存储。属性名以 `.` 分割后的每个片段都会成为 trie 中的一个节点。在同一层级内，兄弟节点又按照二叉搜索树组织，以提升查找效率。

源码中的经典注释展示了这个结构：

```c
// Source: bionic/libc/system_properties/include/system_properties/prop_area.h
//
// Properties are stored in a hybrid trie/binary tree structure.
// Each property's name is delimited at '.' characters, and the tokens are put
// into a trie structure.  Siblings at each level of the trie are stored in a
// binary tree.  For instance, "ro.secure"="1" could be stored as follows:
//
// +-----+   children    +----+   children    +--------+
// |     |-------------->| ro |-------------->| secure |
// +-----+               +----+               +--------+
//                       /    \                /   |
//                 left /      \ right   left /    |  prop   +===========+
//                     v        v            v     +-------->| ro.secure |
//                  +-----+   +-----+     +-----+            +-----------+
//                  | net |   | sys |     | com |            |     1     |
//                  +-----+   +-----+     +-----+            +===========+
```

`prop_trie_node` 结构如下：

```c
// Source: bionic/libc/system_properties/include/system_properties/prop_area.h
struct prop_trie_node {
    uint32_t namelen;

    // 原子“指针”（实际上是相对于 data_ 基地址的偏移量）
    // 使用 release-consume 顺序保证线程安全
    atomic_uint_least32_t prop;       // -> 如果属性在此处存在，指向 prop_info
    atomic_uint_least32_t left;       // -> 指向 BST 中的左子节点
    atomic_uint_least32_t right;      // -> 指向 BST 中的右子节点
    atomic_uint_least32_t children;   // -> 指向 trie 的下一层（第一个子节点）

    char name[0];                     // 柔性数组：片段名称

    prop_trie_node(const char* name, const uint32_t name_length) {
        this->namelen = name_length;
        memcpy(this->name, name, name_length);
        this->name[name_length] = '\0';
    }
};
```

```mermaid
graph TD
    ROOT["Root Node<br/>(empty)"]

    RO["ro<br/>prop_trie_node"]
    SYS["sys<br/>prop_trie_node"]
    PERSIST["persist<br/>prop_trie_node"]
    NET["net<br/>prop_trie_node"]
    DEBUG["debug<br/>prop_trie_node"]

    RO_BUILD["build<br/>prop_trie_node"]
    RO_PRODUCT["product<br/>prop_trie_node"]
    RO_HARDWARE["hardware<br/>prop_trie_node"]
    RO_BOOT["boot<br/>prop_trie_node"]
    RO_SECURE["secure<br/>prop_trie_node"]

    RO_BUILD_FP["fingerprint<br/>prop_trie_node"]
    RO_BUILD_TYPE["type<br/>prop_trie_node"]

    PI_SECURE["prop_info<br/>ro.secure = 1"]
    PI_FP["prop_info<br/>ro.build.fingerprint =<br/>google/raven/..."]
    PI_TYPE["prop_info<br/>ro.build.type = userdebug"]

    ROOT -->|children| RO
    RO -->|right BST| SYS
    SYS -->|right BST| PERSIST
    RO -->|left BST| NET
    NET -->|left BST| DEBUG

    RO -->|children| RO_BUILD
    RO_BUILD -->|right BST| RO_PRODUCT
    RO_PRODUCT -->|right BST| RO_HARDWARE
    RO_BUILD -->|left BST| RO_BOOT
    RO_HARDWARE -->|right BST| RO_SECURE

    RO_BUILD -->|children| RO_BUILD_FP
    RO_BUILD_FP -->|right BST| RO_BUILD_TYPE

    RO_SECURE -->|prop| PI_SECURE
    RO_BUILD_FP -->|prop| PI_FP
    RO_BUILD_TYPE -->|prop| PI_TYPE

    style ROOT fill:#2d3436,color:#fff
    style PI_SECURE fill:#00b894,color:#fff
    style PI_FP fill:#00b894,color:#fff
    style PI_TYPE fill:#00b894,color:#fff
```

`find_property` 方法通过遍历该前缀树（trie）来定位属性：

```c
// Source: bionic/libc/system_properties/prop_area.cpp
const prop_info* prop_area::find_property(prop_trie_node* const trie,
    const char* name, uint32_t namelen,
    const char* value, uint32_t valuelen, bool alloc_if_needed) {
    if (!trie) return nullptr;

    const char* remaining_name = name;
    prop_trie_node* current = trie;
    while (true) {
        const char* sep = strchr(remaining_name, '.');
        const bool want_subtree = (sep != nullptr);
        const uint32_t substr_size = (want_subtree)
            ? sep - remaining_name : strlen(remaining_name);

        if (!substr_size) return nullptr;

        // 导航到子节点，如果需要则创建
        prop_trie_node* root = nullptr;
        uint_least32_t children_offset =
            atomic_load_explicit(&current->children, memory_order_relaxed);
        if (children_offset != 0) {
            root = to_prop_trie_node(&current->children);
        } else if (alloc_if_needed) {
            uint_least32_t new_offset;
            root = new_prop_trie_node(remaining_name, substr_size, &new_offset);
            if (root) {
                atomic_store_explicit(&current->children, new_offset,
                                      memory_order_release);
            }
        }
        if (!root) return nullptr;

        // 在兄弟节点之间进行二分查找
        current = find_prop_trie_node(root, remaining_name, substr_size,
                                       alloc_if_needed);
        if (!current) return nullptr;
        if (!want_subtree) break;
        remaining_name = sep + 1;
    }

    // 检查此节点是否附加了 prop_info
    uint_least32_t prop_offset =
        atomic_load_explicit(&current->prop, memory_order_relaxed);
    if (prop_offset != 0) {
        return to_prop_info(&current->prop);
    } else if (alloc_if_needed) {
        // 分配新的 prop_info
        ...
    }
    return nullptr;
}
```

对于像 `ro.build.fingerprint` 这样的属性名，查找过程如下：

1. 从根节点开始，下降到子节点。
2. 在子节点中二分查找 `ro` 片段。
3. 下降到 `ro` 的子节点，二分查找 `build`。
4. 下降到 `build` 的子节点，二分查找 `fingerprint`。
5. 返回附加在 `fingerprint` 节点上的 `prop_info`。

兄弟节点之间的二分查找实现在 `find_prop_trie_node` 中：

```c
// Source: bionic/libc/system_properties/prop_area.cpp
prop_trie_node* prop_area::find_prop_trie_node(prop_trie_node* const trie,
    const char* name, uint32_t namelen, bool alloc_if_needed) {
    prop_trie_node* current = trie;
    while (true) {
        if (!current) return nullptr;
        const int ret = cmp_prop_name(name, namelen, current->name,
                                       current->namelen);
        if (ret == 0) return current;        // 找到
        if (ret < 0) {                       // 向左走
            uint_least32_t left_offset =
                atomic_load_explicit(&current->left, memory_order_relaxed);
            if (left_offset != 0) {
                current = to_prop_trie_node(&current->left);
            } else {
                if (!alloc_if_needed) return nullptr;
                // 在左侧分配新节点
                ...
            }
        } else {                             // 向右走
            ...
        }
    }
}
```

### 6.1.5 `prop_info` 结构

每个真实属性值都存储在一个 `prop_info` 结构中，定义在 `bionic/libc/system_properties/include/system_properties/prop_info.h`：

```c
struct prop_info {
    static constexpr uint32_t kLongFlag = 1 << 16;
    static constexpr size_t kLongLegacyErrorBufferSize = 56;

    atomic_uint_least32_t serial;
    union {
        char value[PROP_VALUE_MAX];
        struct {
            char error_message[kLongLegacyErrorBufferSize];
            uint32_t offset;
        } long_property;
    };
    char name[0];
};
```

`serial` 字段同时承担多种职责：

- **bit 0（dirty bit）**：写入进行中时置 1，读取者看到 dirty serial 后读取备份区。
- **bit 16（long flag）**：当值超过 `PROP_VALUE_MAX` 时置 1，只读属性可通过该机制存储长值。
- **bit 24-31（value length）**：高 8 位编码当前值长度。
- **其余位**：单调递增计数器。

`prop_info` 的内存布局如下：

```text
+----------------------------+  offset 0
|  serial (4B, atomic)       |  Dirty bit | Long flag | Length | Counter
+----------------------------+  offset 4
|  value[92] or              |  短值内联存储
|  { error_msg[56], offset } |  长值使用偏移寻址
+----------------------------+  offset 96
|  name[]                    |  完整属性名，以 NUL 结尾
+----------------------------+
```

### 6.1.6 无等待（Wait-Free）读取协议

系统属性机制实现了一套复杂的无等待（Wait-Free）读取协议，确保即使在写入正在进行时，读取者也永远不会阻塞。该协议依赖于 `serial` 字段和“脏数据备份区（dirty backup area）”。

当 init 需要更新属性时，它在 `bionic/libc/system_properties/system_properties.cpp` 中遵循以下序列：

```c
// Source: bionic/libc/system_properties/system_properties.cpp
int SystemProperties::Update(prop_info* pi, const char* value, unsigned int len) {
    ...
    uint32_t serial = atomic_load_explicit(&pi->serial, memory_order_relaxed);
    unsigned int old_len = SERIAL_VALUE_LEN(serial);

    // 步骤 1：将旧值拷贝到脏数据备份区
    memcpy(pa->dirty_backup_area(), pi->value, old_len + 1);

    // 步骤 2：设置脏位（bit 0 = 1）
    serial |= 1;
    atomic_store_explicit(&pi->serial, serial, memory_order_release);

    // 步骤 3：在更新值之前设置内存屏障（Memory fence）
    atomic_thread_fence(memory_order_release);

    // 步骤 4：将新值拷贝到 prop_info 中
    memcpy(pi->value, value, len + 1);

    // 步骤 5：清除脏位，更新长度和计数器
    int new_serial = (len << 24) | ((serial + 1) & 0xffffff);
    atomic_store_explicit(&pi->serial, new_serial, memory_order_release);

    // 步骤 6：通过 futex 唤醒等待者
    __futex_wake(&pi->serial, INT32_MAX);

    // 步骤 7：递增全局区域序列号
    atomic_store_explicit(serial_pa->serial(),
        atomic_load_explicit(serial_pa->serial(), memory_order_relaxed) + 1,
        memory_order_release);
    __futex_wake(serial_pa->serial(), INT32_MAX);
    return 0;
}
```

在读取端，`ReadMutablePropertyValue` 处理脏位逻辑：

```c
// Source: bionic/libc/system_properties/system_properties.cpp
uint32_t SystemProperties::ReadMutablePropertyValue(const prop_info* pi, char* value) {
    uint32_t new_serial = load_const_atomic(&pi->serial, memory_order_acquire);
    uint32_t serial;
    unsigned int len;
    for (;;) {
        serial = new_serial;
        len = SERIAL_VALUE_LEN(serial);
        if (__predict_false(SERIAL_DIRTY(serial))) {
            // 写入者正在更新中：改为从备份区读取旧值
            prop_area* pa = contexts_->GetPropAreaForName(pi->name);
            memcpy(value, pa->dirty_backup_area(), len + 1);
        } else {
            memcpy(value, pi->value, len + 1);
        }
        atomic_thread_fence(memory_order_acquire);
        new_serial = load_const_atomic(&pi->serial, memory_order_relaxed);
        if (__predict_true(serial == new_serial)) {
            break;  // 序列号未变：读取一致
        }
        // 读取期间序列号发生了变化：重试
        atomic_thread_fence(memory_order_acquire);
    }
    return serial;
}
```

```mermaid
sequenceDiagram
    participant Writer as init (写入者)
    participant SHM as 共享内存
    participant Reader as 进程 (读取者)

    Note over SHM: serial=0x01000002<br/>value="old_val"

    Writer->>SHM: 将旧值拷贝到脏数据备份区
    Writer->>SHM: 设置序列号脏位 (serial |= 1)
    Writer->>SHM: 将新值 memcpy 到 prop_info

    Reader->>SHM: 加载序列号 (看到脏位已设置)
    Reader->>SHM: 从脏数据备份区读取 ("old_val")
    Reader->>SHM: 重新加载序列号
    Note over Reader: 序列号已变 -> 重试

    Writer->>SHM: 更新序列号：新长度 + 清除脏位
    Writer->>SHM: futex_wake()

    Reader->>SHM: 加载序列号 (脏位已清除)
    Reader->>SHM: 从 prop_info 读取值 ("new_val")
    Reader->>SHM: 重新加载序列号 (匹配 -> 成功)
    Note over Reader: 读取完成: "new_val"
```

只读属性（`ro.*`）获得了一项优化：由于它们在设置后永远不会改变，读取者可以完全跳过脏位协议：

```c
// Source: bionic/libc/system_properties/system_properties.cpp
void SystemProperties::ReadCallback(const prop_info* pi,
    void (*callback)(void* cookie, const char* name,
                     const char* value, uint32_t serial),
    void* cookie) {
    if (is_read_only(pi->name)) {
        // 只读：无需脏位检查
        uint32_t serial = load_const_atomic(&pi->serial, memory_order_relaxed);
        if (pi->is_long()) {
            callback(cookie, pi->name, pi->long_value(), serial);
        } else {
            callback(cookie, pi->name, pi->value, serial);
        }
        return;
    }
    // 可变属性：使用完整的读取协议
    char value_buf[PROP_VALUE_MAX];
    uint32_t serial = ReadMutablePropertyValue(pi, value_buf);
    callback(cookie, pi->name, value_buf, serial);
}
```

### 6.1.7 长属性值

历史上，属性值受 `PROP_VALUE_MAX`（92 字节）限制。从 Android O 开始，只读属性（`ro.*`）可以使用 “long property” 机制存储更长的值。当 value 长度超过 `PROP_VALUE_MAX` 时，serial 中的 `kLongFlag`（bit 16）会被置位，真实值存储在 property area 中的另一段偏移位置。

```c
prop_info* prop_area::new_prop_info(const char* name, uint32_t namelen,
    const char* value, uint32_t valuelen, uint_least32_t* const off) {
    if (valuelen >= PROP_VALUE_MAX) {
        uint32_t long_value_offset = 0;
        char* long_location = reinterpret_cast<char*>(
            allocate_obj(valuelen + 1, &long_value_offset));
        memcpy(long_location, value, valuelen);
        long_location[valuelen] = '\0';
        long_value_offset -= new_offset;
        info = new (p) prop_info(name, namelen, long_value_offset);
    } else {
        info = new (p) prop_info(name, namelen, value, valuelen);
    }
}
```

`prop_info::long_value()` 通过相对偏移还原指针：

```c
const char* long_value() const {
    return reinterpret_cast<const char*>(this) + long_property.offset;
}
```

这使 `ro.build.fingerprint` 这类很长的只读属性可以完整存储，避免被截断。

### 6.1.8 `property_info` Trie（SELinux Context Trie）

除了保存实际值的 property value trie 外，还有第二棵 trie，用于把属性名映射到 SELinux context 与类型信息。这就是 `property_info` trie，会被序列化到 `/dev/__properties__/property_info`。

init 启动时从多个 `property_contexts` 文件构建它：

```c
// Source: system/core/init/property_service.cpp
void CreateSerializedPropertyInfo() {
    auto property_infos = std::vector<PropertyInfoEntry>();

    // 加载平台属性上下文
    if (access("/system/etc/selinux/plat_property_contexts", R_OK) != -1) {
        LoadPropertyInfoFromFile(
            "/system/etc/selinux/plat_property_contexts", &property_infos);

        // 加载分区专属上下文
        LoadPropertyInfoFromFile(
            "/system_ext/etc/selinux/system_ext_property_contexts", ...);
        LoadPropertyInfoFromFile(
            "/vendor/etc/selinux/vendor_property_contexts", ...);
        LoadPropertyInfoFromFile(
            "/product/etc/selinux/product_property_contexts", ...);
        LoadPropertyInfoFromFile(
            "/odm/etc/selinux/odm_property_contexts", ...);
    }
    ...

    // 序列化为紧凑的二进制格式
    auto serialized_contexts = std::string();
    auto error = std::string();
    if (!BuildTrie(property_infos, "u:object_r:default_prop:s0", "string",
                   &serialized_contexts, &error)) {
        LOG(ERROR) << "Unable to serialize property contexts: " << error;
        return;
    }

    // 写入到 /dev/__properties__/property_info
    WriteStringToFile(serialized_contexts, PROP_TREE_FILE, 0444, 0, 0, false);
    selinux_android_restorecon(PROP_TREE_FILE, 0);
}
```

序列化后的 `property_info` trie 定义在 `system/core/property_service/libpropertyinfoparser/include/property_info_parser/property_info_parser.h` 中：

```c
// Source: system/core/property_service/libpropertyinfoparser/.../property_info_parser.h
struct PropertyInfoAreaHeader {
    uint32_t current_version;
    uint32_t minimum_supported_version;
    uint32_t size;
    uint32_t contexts_offset;     // -> 指向 SELinux context 字符串数组
    uint32_t types_offset;        // -> 指向类型字符串数组
    uint32_t root_offset;         // -> 根 TrieNodeInternal
};

struct TrieNodeInternal {
    uint32_t property_entry;      // -> 此节点的 PropertyEntry
    uint32_t num_child_nodes;
    uint32_t child_nodes;         // -> 已排序的子节点偏移量数组
    uint32_t num_prefixes;
    uint32_t prefix_entries;      // -> 前缀匹配条目
    uint32_t num_exact_matches;
    uint32_t exact_match_entries; // -> 精确匹配条目
};

struct PropertyEntry {
    uint32_t name_offset;
    uint32_t namelen;
    uint32_t context_index;       // contexts 数组中的索引
    uint32_t type_index;          // types 数组中的索引
};
```

```mermaid
graph TB
    subgraph "property_info 文件 (/dev/__properties__/property_info)"
        HDR["PropertyInfoAreaHeader<br/>version, size<br/>contexts_offset<br/>types_offset<br/>root_offset"]

        CTX_ARRAY["Contexts Array<br/>[0] u:object_r:default_prop:s0<br/>[1] u:object_r:system_prop:s0<br/>[2] u:object_r:radio_prop:s0<br/>[3] u:object_r:debug_prop:s0<br/>..."]

        TYPE_ARRAY["Types Array<br/>[0] string<br/>[1] bool<br/>[2] int<br/>[3] uint<br/>..."]

        ROOT["Root TrieNodeInternal<br/>children: [ro, sys, net, persist, debug, ...]"]

        RO_NODE["'ro' TrieNodeInternal<br/>context_index: 1<br/>prefix_entries: [...]<br/>children: [build, product, ...]"]

        DEBUG_NODE["'debug' TrieNodeInternal<br/>context_index: 3<br/>type_index: 0 (string)"]
    end

    HDR --> CTX_ARRAY
    HDR --> TYPE_ARRAY
    HDR --> ROOT
    ROOT --> RO_NODE
    ROOT --> DEBUG_NODE

    style HDR fill:#0984e3,color:#fff
    style CTX_ARRAY fill:#6c5ce7,color:#fff
    style TYPE_ARRAY fill:#6c5ce7,color:#fff
```

当进程调用 `__system_property_find("debug.myapp.trace")` 时，bionic 库：

1. 查找 `property_info` trie 以找到 `debug.*` 的 SELinux context 索引。
2. 使用该索引打开 `/dev/__properties__/` 下正确的 property area 文件。
3. 在该区域内的属性值 trie 中搜索实际值。

这种两级查找机制确保了每个 SELinux context 映射到其自己的内存映射文件，从而使内核能够在文件级别强制执行读取权限。

---

## 6.2 属性命名空间

Android 系统属性遵循层级命名约定。前缀决定了属性的可变性、持久化行为和访问控制。理解这些命名空间是使用平台属性机制的基础。

### 6.2.1 只读属性（`ro.*`）

以 `ro.` 开头的属性是 “write-once” 属性：启动期间可以设置，但之后不能修改。强制逻辑位于 `system/core/init/property_service.cpp`：

```c
static std::optional<uint32_t> PropertySet(const std::string& name,
    const std::string& value, SocketConnection* socket, std::string* error) {
    prop_info* pi = (prop_info*)__system_property_find(name.c_str());
    if (pi != nullptr) {
        if (StartsWith(name, "ro.")) {
            *error = "Read-only property was already set";
            return {PROP_ERROR_READ_ONLY_PROPERTY};
        }
        __system_property_update(pi, value.c_str(), valuelen);
    } else {
        __system_property_add(name.c_str(), name.size(), value.c_str(), valuelen);
    }
}
```

`ro.*` 属性的关键特征如下：

- **首次设置后不可变。** 已存在的 `ro.*` 再次设置会返回 `PROP_ERROR_READ_ONLY_PROPERTY`。
- **支持长值。** 与可变属性不同，`ro.*` 可以通过 long property 机制存储超过 `PROP_VALUE_MAX` 的值。
- **读取路径优化。** 由于设置后不会变化，读取者跳过 dirty-bit 协议。
- **启动期间设置。** 通常来自 `build.prop`、kernel command line（`androidboot.*`）和 device tree。

常见 `ro.*` 属性如下：

| 属性 | 说明 | 示例值 |
|----------|-------------|---------------|
| `ro.build.fingerprint` | 唯一构建标识 | `google/raven/raven:14/...` |
| `ro.build.type` | 构建类型 | `userdebug`, `user`, `eng` |
| `ro.build.version.sdk` | API level | `34` |
| `ro.product.model` | 设备型号 | `Pixel 6 Pro` |
| `ro.product.manufacturer` | 设备厂商 | `Google` |
| `ro.hardware` | 硬件平台 | `tensor` |
| `ro.debuggable` | Debug 构建标记 | `1` 或 `0` |
| `ro.secure` | 安全执行标记 | `1` |
| `ro.boot.serialno` | 设备序列号 | 设备相关 |
| `ro.vendor.api_level` | Vendor API level | `34` |

### 6.2.2 持久化属性（`persist.*`）

以 `persist.` 开头的属性会自动保存到磁盘，并在重启后恢复。持久化机制由 `system/core/init/persistent_properties.cpp` 实现。

存储文件是 `/data/property/persistent_properties`，编码格式为 Protocol Buffer：

```c
// Source: system/core/init/persistent_properties.cpp
[[clang::no_destroy]] std::string persistent_property_filename =
    "/data/property/persistent_properties";
```

当设置 `persist.*` 属性时，`PropertySet()` 会触发写入：

```c
// Source: system/core/init/property_service.cpp
bool need_persist = StartsWith(name, "persist.") || StartsWith(name, "next_boot.");
if (socket && persistent_properties_loaded && need_persist) {
    if (persist_write_thread) {
        persist_write_thread->Write(name, value, std::move(*socket));
        return {};  // 响应在写入完成后异步发送
    }
    WritePersistentProperty(name, value);
}
```

写入操作会读取整个 protobuf 文件，更新相关条目，然后使用 rename 原子地写回：

```c
// Source: system/core/init/persistent_properties.cpp
void WritePersistentProperty(const std::string& name, const std::string& value) {
    auto persistent_properties = LoadPersistentPropertyFile();
    if (!persistent_properties.ok()) {
        // 如果文件损坏，从内存中恢复
        persistent_properties = LoadPersistentPropertiesFromMemory();
    }

    // 查找并更新，或添加新条目
    auto it = std::find_if(...);
    if (it != persistent_properties->mutable_properties()->end()) {
        it->set_value(value);
    } else {
        AddPersistentProperty(name, value, &persistent_properties.value());
    }

    WritePersistentPropertyFile(*persistent_properties);
}
```

磁盘写入采用了标准的原子重命名模式：

```c
// Source: system/core/init/persistent_properties.cpp
Result<void> WritePersistentPropertyFile(
    const PersistentProperties& persistent_properties) {
    const std::string temp_filename = persistent_property_filename + ".tmp";
    unique_fd fd(TEMP_FAILURE_RETRY(
        open(temp_filename.c_str(),
             O_WRONLY | O_CREAT | O_NOFOLLOW | O_TRUNC | O_CLOEXEC, 0600)));
    ...
    std::string serialized_string;
    persistent_properties.SerializeToString(&serialized_string);
    WriteStringToFd(serialized_string, fd);
    fsync(fd.get());
    fd.reset();

    // 原子重命名
    rename(temp_filename.c_str(), persistent_property_filename.c_str());

    // 对目录进行 fsync 以确保持久性
    auto dir_fd = unique_fd{open(dir.c_str(), O_DIRECTORY | O_RDONLY | O_CLOEXEC)};
    fsync(dir_fd.get());
    return {};
}
```

为了提高性能，系统提供了一个异步写入线程。当 `ro.property_service.async_persist_writes` 为 `true` 时，init 会将持久化写入委托给专用的 `PersistWriteThread`：

```c
// Source: system/core/init/property_service.cpp
class PersistWriteThread {
  public:
    void Write(std::string name, std::string value, SocketConnection socket);
  private:
    void Work() {
        while (true) {
            std::tuple<std::string, std::string, SocketConnection> item;
            {
                std::unique_lock<std::mutex> lock(mutex_);
                while (work_.empty()) { cv_.wait(lock); }
                item = std::move(work_.front());
                work_.pop_front();
            }
            WritePersistentProperty(std::get<0>(item), std::get<1>(item));
            NotifyPropertyChange(std::get<0>(item), std::get<1>(item));
            std::get<2>(item).SendUint32(PROP_SUCCESS);
        }
    }
    std::thread thread_;
    std::mutex mutex_;
    std::condition_variable cv_;
    std::deque<std::tuple<std::string, std::string, SocketConnection>> work_;
};
```

### 6.2.3 阶段化属性（`next_boot.*`）

`next_boot.` 前缀用于暂存下一次重启后才生效的属性变化。它们和 `persist.*` 属性一起保存在同一个 protobuf 文件中，但启动时会被“应用”为对应的 `persist.*` 值。

```c
auto const staged_prefix = std::string_view("next_boot.");
for (const auto& property_record : persistent_properties->properties()) {
    auto const& prop_name = property_record.name();
    if (StartsWith(prop_name, staged_prefix)) {
        auto actual_prop_name = prop_name.substr(staged_prefix.size());
        staged_props[actual_prop_name] = property_record.value();
    }
}
```

例如设置 `next_boot.persist.sys.language=fr`，会让下一次启动时的 `persist.sys.language` 变成 `fr`。应用后，`next_boot.*` 条目会被移除。

### 6.2.4 系统运行时属性（`sys.*`）

`sys.*` 命名空间用于反映当前系统状态的运行时属性。这些属性可变，但不会跨重启持久化。

| 属性 | 说明 |
|----------|-------------|
| `sys.boot_completed` | 启动完成后设置为 `1` |
| `sys.powerctl` | 触发重启或关机 |
| `sys.oem_unlock_allowed` | OEM unlock 策略 |
| `sys.sysctl.extra_free_kbytes` | 内存调优参数 |

`sys.powerctl` 是特殊属性，设置它会触发设备重启或关机。property service 会记录发起设置的进程信息，以便审计。

### 6.2.5 Vendor 属性（`vendor.*`）

`vendor.*` 前缀保留给 vendor 专用属性。这些属性受 Project Treble 引入的 Vendor Interface（VINTF）属性命名空间隔离规则约束。第 6.7 节会详细说明。

### 6.2.6 Debug 属性（`debug.*`）

`debug.*` 命名空间通常用于开发和调试。相较系统属性，它的 SELinux 策略更宽松，使开发者可以在 `userdebug` 构建上通过 `adb shell setprop` 设置这些属性。

```text
# Source: system/sepolicy/private/property_contexts
debug.                  u:object_r:debug_prop:s0
debug.db.               u:object_r:debuggerd_prop:s0
```

### 6.2.7 控制属性（`ctl.*`）

`ctl.*` 并不是常规属性命名空间。property service 会拦截这些属性，用它们控制 init service：

```c
if (StartsWith(name, "ctl.")) {
    return {SendControlMessage(name.c_str() + 4, value, cr.pid, socket, error)};
}
```

设置 `ctl.start=<service_name>` 会启动服务，`ctl.stop=<service_name>` 会停止服务，`ctl.restart=<service_name>` 会重启服务。这类操作的权限检查基于目标 service 的 SELinux context。

### 6.2.8 服务状态属性（`init.svc.*`）

init 会自动维护 `init.svc.<service_name>` 属性，用于反映每个服务的状态：`stopped`、`starting`、`running`、`stopping`、`restarting`。

### 6.2.9 命名空间行为总结

```mermaid
graph LR
    RO["ro.*<br/>写一次<br/>启动期设置<br/>支持长值<br/>读取优化"]
    PERSIST["persist.*<br/>可读写<br/>跨重启保留<br/>protobuf 存储<br/>异步写入"]
    SYS["sys.*<br/>可读写<br/>运行时状态<br/>不持久化"]
    VENDOR["vendor.*<br/>可读写<br/>vendor 分区<br/>Treble 隔离"]
    DEBUG["debug.*<br/>可读写<br/>shell 可访问<br/>开发调试"]
    CTL["ctl.*<br/>只写<br/>控制 init service<br/>特殊权限"]
```

---

## 6.3 Property Contexts 与 SELinux 集成

### 6.3.1 `property_contexts` 文件格式

`property_contexts` 文件把属性名前缀映射到 SELinux context 与类型。典型条目如下：

```text
# prefix/exact-name          SELinux context                 type
ro.build.                    u:object_r:build_prop:s0        exact string
persist.sys.                 u:object_r:system_prop:s0       string
debug.                       u:object_r:debug_prop:s0        string
vendor.                      u:object_r:vendor_prop:s0       string
```

这些 context 决定了：

- 属性写入时需要哪些 `property_service { set }` 权限。
- 属性读取时 property area 文件需要哪些 `file { read }` 权限。
- 属性 value 需要满足哪种类型约束，例如 `bool`、`int`、`uint`、`enum` 或 `string`。

### 6.3.2 分区专属 Context 文件

Android 会从多个分区加载 property context：

| 文件 | 作用域 |
|------|--------|
| `/system/etc/selinux/plat_property_contexts` | 平台属性 |
| `/system_ext/etc/selinux/system_ext_property_contexts` | system_ext 属性 |
| `/vendor/etc/selinux/vendor_property_contexts` | vendor 属性 |
| `/product/etc/selinux/product_property_contexts` | product 属性 |
| `/odm/etc/selinux/odm_property_contexts` | ODM 属性 |

init 把这些文件合并成序列化 `property_info` trie，并写入 `/dev/__properties__/property_info`。

### 6.3.3 属性写入的 SELinux 强制执行

写入属性时，property service 会取得调用方的 SELinux context，再检查调用方是否有权设置目标属性：

```c
static bool CheckMacPerms(const std::string& name, const char* target_context,
                          const char* source_context, const ucred& cr) {
    PropertyAuditData audit_data;
    audit_data.name = name.c_str();
    audit_data.cr = &cr;
    return selinux_check_access(source_context, target_context,
                                "property_service", "set", &audit_data) == 0;
}
```

权限模型的含义是：调用方进程域必须对目标属性 context 拥有 `property_service set` 权限。以普通 app 为例，它即使能连接 property_service socket，也会因为缺少 SELinux 权限而无法设置大多数系统属性。

### 6.3.4 属性读取的 SELinux 强制执行

读取权限通过文件访问控制实现。每个 SELinux context 对应一个独立 property area 文件，这些文件本身带有相应 SELinux label。进程要读取某类属性，就必须能读取对应文件。

这种设计把读取路径保持在无 IPC、无锁的共享内存访问上，同时仍然利用内核的文件权限和 SELinux 权限做强制隔离。

### 6.3.5 类型检查

`property_contexts` 中可以声明属性类型。property service 在设置属性时会对 value 做类型检查，避免把布尔属性写成任意字符串，或把整数属性写成非法文本。

常见类型包括：

| 类型 | 说明 | 示例 |
|------|------|------|
| `string` | 任意字符串 | `userdebug` |
| `bool` | 布尔值 | `true`, `false`, `1`, `0` |
| `int` | 有符号整数 | `-1`, `42` |
| `uint` | 无符号整数 | `0`, `4096` |
| `double` | 浮点数 | `0.75` |
| `enum` | 枚举值 | `disabled`, `filtered`, `full` |

类型检查把属性从“任意字符串开关”提升为具备基本 schema 的系统接口。

### 6.3.6 Appcompat Override 机制

系统属性服务还支持 appcompat override 机制，用于在兼容性场景下覆盖部分属性行为。这类机制通常服务于平台迁移和兼容性开关，允许系统在不改变基础属性定义的情况下，对特定应用或场景施加额外行为。

---

## 6.4 Init 中的 PropertyService

### 6.4.1 初始化序列

property service 的启动分为两个阶段：首先初始化共享内存和属性上下文，然后启动 socket 线程以接受写入请求。

```mermaid
graph TD
    A["PropertyInit()"] --> B["设置 SELinux audit callback"]
    B --> C["mkdir /dev/__properties__"]
    C --> D["CreateSerializedPropertyInfo()"]
    D --> E["__system_property_area_init()"]
    E --> F["加载默认路径的 property_info"]
    F --> G["ProcessKernelCmdline()"]
    G --> H["ProcessBootconfig()"]
    H --> I["ExportKernelBootProps()"]
    I --> J["PropertyLoadBootDefaults()"]
    J --> K["PropertyLoadDerivedDefaults()"]

    L["StartPropertyService()"] --> M["设置 ro.property_service.version=2"]
    M --> N["socketpair()"]
    N --> O["启动 property_service_for_system 线程"]
    O --> P["启动 property_service 线程"]
    P --> Q["启动 PersistWriteThread（可选）"]
```

### 6.4.2 加载启动属性

`PropertyLoadBootDefaults()` 负责按正确顺序加载所有属性文件。顺序非常重要，因为后加载的、来自更具体分区的属性会覆盖先加载的、更通用分区的属性。

```c
// Source: system/core/init/property_service.cpp
void PropertyLoadBootDefaults() {
    std::map<std::string, std::string> properties;
    LoadPropertiesFromSecondStageRes(&properties);
    load_properties_from_file("/system/build.prop", nullptr, &properties);
    load_properties_from_partition("system_ext", 30);
    load_properties_from_file("/system_dlkm/etc/build.prop", nullptr, &properties);
    load_properties_from_file("/vendor/default.prop", nullptr, &properties);
    load_properties_from_file("/vendor/build.prop", nullptr, &properties);
    load_properties_from_file("/vendor_dlkm/etc/build.prop", nullptr, &properties);
    load_properties_from_file("/odm_dlkm/etc/build.prop", nullptr, &properties);
    load_properties_from_partition("odm", 28);
    load_properties_from_partition("product", 30);

    for (const auto& [name, value] : properties) {
        std::string error;
        PropertySetNoSocket(name, value, &error);
    }

    property_initialize_ro_product_props();
    property_derive_build_fingerprint();
    property_initialize_ro_cpu_abilist();
    property_initialize_ro_vendor_api_level();
    update_sys_usb_config();
}
```

属性加载的优先级从低到高依次为：

1. `/system/build.prop`
2. `/system_ext/etc/build.prop`
3. `/system_dlkm/etc/build.prop`
4. `/vendor/default.prop` 与 `/vendor/build.prop`
5. `/vendor_dlkm/etc/build.prop`
6. `/odm_dlkm/etc/build.prop`
7. `/odm/etc/build.prop`
8. `/product/etc/build.prop`

### 6.4.3 内核命令行（Kernel Command Line）处理

init 会将内核命令行和 bootconfig 中的 `androidboot.*` 参数转换为 `ro.boot.*` 属性：

```c
// Source: system/core/init/property_service.cpp
constexpr auto ANDROIDBOOT_PREFIX = "androidboot."sv;

static void ProcessKernelCmdline() {
    android::fs_mgr::ImportKernelCmdline(
        [&](const std::string& key, const std::string& value) {
            if (StartsWith(key, ANDROIDBOOT_PREFIX)) {
                InitPropertySet("ro.boot." + key.substr(ANDROIDBOOT_PREFIX.size()), value);
            }
        });
}
```

随后 `ExportKernelBootProps()` 会创建一些遗留别名，以保证兼容性：

```c
// Source: system/core/init/property_service.cpp
static void ExportKernelBootProps() {
    struct { const char* src_prop; const char* dst_prop; const char* default_value; } prop_map[] = {
        { "ro.boot.serialno",   "ro.serialno",   ""        },
        { "ro.boot.mode",       "ro.bootmode",   "unknown" },
        { "ro.boot.baseband",   "ro.baseband",   "unknown" },
        { "ro.boot.bootloader", "ro.bootloader", "unknown" },
        { "ro.boot.hardware",   "ro.hardware",   "unknown" },
        { "ro.boot.revision",   "ro.revision",   "0"       },
    };
    ...
}
```

### 6.4.4 基于 Socket 的写入 API

property service 通过两个 Unix domain socket 接受写入请求：

```c
// Source: system/core/init/property_service.cpp
void StartPropertyService(int* epoll_socket) {
    InitPropertySet("ro.property_service.version", "2");
    socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, sockets);
    StartThread(PROP_SERVICE_FOR_SYSTEM_NAME, 0660, AID_SYSTEM,
                property_service_for_system_thread, true);
    StartThread(PROP_SERVICE_NAME, 0666, 0,
                property_service_thread, false);
}
```

这两个 socket 的职责分工如下：

- **`property_service_for_system`**（权限 0660）：仅供 system 组的进程访问。它也监听来自 init 内部的消息，例如加载持久化属性的请求。
- **`property_service`**（权限 0666）：对所有进程开放，是通用的属性设置接口。

每个 socket 都在独立的 epoll 线程中运行，负责接收连接、解析消息、检查调用方凭据，并执行最终的属性设置逻辑。

### 6.4.5 传输协议（Wire Protocol）

属性设置协议支持两种消息类型：

**`PROP_MSG_SETPROP`（遗留消息）：**

```text
[uint32_t cmd=1] [char name[PROP_NAME_MAX]] [char value[PROP_VALUE_MAX]]
```

它使用固定长度字段，且没有响应信息，主要供旧版 bionic 使用。

**`PROP_MSG_SETPROP2`（当前消息）：**

```text
[uint32_t cmd=2] [uint32_t name_len] [char name[]] [uint32_t value_len] [char value[]]
```

它使用带长度前缀的字符串，并会返回一个 uint32 类型的响应码。property service 通过 `SO_PEERCRED` 获取调用方的 `pid`、`uid` 和 `gid`，随后基于调用方的 SELinux 上下文和属性上下文执行权限检查。

### 6.4.6 属性变化通知

属性成功设置后，init 可以触发在 `.rc` 文件中定义的动作（action）。每次成功设置属性后，都会调用 `NotifyPropertyChange()`：

```c
// Source: system/core/init/property_service.cpp
void NotifyPropertyChange(const std::string& name, const std::string& value) {
    auto lock = std::lock_guard{accept_messages_lock};
    if (accept_messages) {
        PropertyChanged(name, value);
    }
}
```

这支持了类似如下的 `.rc` 触发器：

```text
on property:sys.boot_completed=1
    start post_boot_service

on property:ro.debuggable=1
    start adbd
```

### 6.4.7 加载持久化属性

持久化属性会在 `/data` 分区挂载后加载。system socket 线程通过接收来自 init 主循环的 protobuf 消息来处理该操作：

```c
// Source: system/core/init/property_service.cpp
static void HandleInitSocket() {
    auto message = ReadMessage(init_socket);
    auto init_message = InitMessage{};
    init_message.ParseFromString(*message);

    switch (init_message.msg_case()) {
    case InitMessage::kLoadPersistentProperties: {
        load_override_properties();
        auto persistent_properties = LoadPersistentProperties();
        for (const auto& property_record : persistent_properties.properties()) {
            InitPropertySet(property_record.name(), property_record.value());
        }
        InitPropertySet("ro.persistent_properties.ready", "true");
        persistent_properties_loaded = true;
        break;
    }
    }
}
```

旧格式曾将每个持久化属性存储为 `/data/property/` 下的单独文件。现代 Android 使用统一的单 protobuf 文件。如果新格式读取失败，迁移逻辑会尝试回退到旧目录格式，成功后写回新格式并清理旧文件。

---

## 6.5 `SystemProperties` Java API

### 6.5.1 Hidden API

Java 层系统属性接口由 `android.os.SystemProperties` 提供，文件位于 `frameworks/base/core/java/android/os/SystemProperties.java`。该类带有 `@SystemApi` 和 `@hide` 标注，因此它不属于公开 SDK，但平台代码和使用 system SDK 的应用可以访问。

```java
@SystemApi
@RavenwoodKeepWholeClass
public class SystemProperties {
    private static final String TAG = "SystemProperties";
    public static final int PROP_VALUE_MAX = 91;
    ...
}
```

### 6.5.2 Get 方法

`SystemProperties` 提供多个类型化 getter：

```java
@NonNull @SystemApi
public static String get(@NonNull String key) {
    if (TRACK_KEY_ACCESS) onKeyAccess(key);
    return native_get(key);
}

@NonNull @SystemApi
public static String get(@NonNull String key, @Nullable String def) {
    if (TRACK_KEY_ACCESS) onKeyAccess(key);
    return native_get(key, def);
}

@SystemApi
public static int getInt(@NonNull String key, int def) {
    if (TRACK_KEY_ACCESS) onKeyAccess(key);
    return native_get_int(key, def);
}
```

还包括 `getLong()`、`getBoolean()` 等变体。Java 方法最终调用 native 方法，再进入 bionic 的 `__system_property_find()` 与 `__system_property_read_callback()`。

### 6.5.3 Set 方法

`set()` 方法会调用 native setter，最终通过 property_service socket 发送写入请求：

```java
@SystemApi
public static void set(@NonNull String key, @Nullable String val) {
    if (val != null && !key.startsWith("ro.") && val.length() > PROP_VALUE_MAX) {
        throw new IllegalArgumentException("value of system property '" + key + "' is longer than " + PROP_VALUE_MAX + " characters");
    }
    native_set(key, val);
}
```

Java 层也保留了可变属性长度限制：非 `ro.*` 属性的 value 不能超过 `PROP_VALUE_MAX`。

### 6.5.4 基于 Handle 的优化访问

为了避免重复按字符串查找属性，`SystemProperties` 支持先查找 handle，再通过 handle 快速读取：

```java
public static Handle find(@NonNull String name) {
    long nativeHandle = native_find(name);
    if (nativeHandle == 0) return null;
    return new Handle(nativeHandle);
}

public static final class Handle {
    private final long mNativeHandle;
    public String get() { return native_get(mNativeHandle); }
    public int getInt(int def) { return native_get_int(mNativeHandle, def); }
    public long getLong(long def) { return native_get_long(mNativeHandle, def); }
    public boolean getBoolean(boolean def) { return native_get_boolean(mNativeHandle, def); }
}
```

这适合频繁读取同一属性的热路径。

### 6.5.5 变化回调

Java API 支持注册属性变化回调：

```java
public static void addChangeCallback(@NonNull Runnable callback) {
    synchronized (sChangeCallbacks) {
        if (sChangeCallbacks.size() == 0) native_add_change_callback();
        sChangeCallbacks.add(callback);
    }
}
```

底层通过 property area 的全局 serial 与 futex 等待机制实现。当任意属性变化时，等待者会被唤醒，Java 层再分发回调。

### 6.5.6 Digest 方法

`digestOf()` 用于对一组属性计算摘要。它读取指定 key 的值，按 key 排序，再把 `key=value` 字符串输入 SHA-1。该方法常用于构建稳定指纹或比较属性集合。

### 6.5.7 NDK 与 Native 访问

native 代码通过 bionic 暴露的 system property API 访问属性：

```c
const prop_info* pi = __system_property_find("ro.build.version.sdk");
if (pi != nullptr) {
    __system_property_read_callback(pi, callback, cookie);
}

char value[PROP_VALUE_MAX];
__system_property_get("ro.product.model", value);
```

实现位于：

```text
bionic/libc/bionic/system_property_api.cpp
bionic/libc/system_properties/system_properties.cpp
```

### 6.5.8 `UnsupportedAppUsage` 与 Greylist

由于历史原因，一些非 SDK 应用曾直接调用 `SystemProperties`。Android 通过 `@UnsupportedAppUsage` 与 greylist 机制在兼容性和 API 封装之间折中：平台可以限制新应用访问隐藏 API，同时允许旧应用在过渡期继续运行。

---

## 6.6 Soong 中的 `sysprop_library`

### 6.6.1 动机：把类型化属性作为 API

直接调用 `SystemProperties.get("some.string.key")` 有几个问题：key 是字符串、value 缺少类型、API 稳定性无法检查、跨分区依赖难以管理。`sysprop_library` 通过 `.sysprop` 声明文件解决这些问题，把系统属性变成可类型检查、可生成代码、可做 API 兼容性检查的接口。

### 6.6.2 `.sysprop` 文件格式

一个 `.sysprop` 文件会声明模块、所有者和属性列表：

```protobuf
module: "android.sysprop.BluetoothProperties"
owner: Platform

prop {
    api_name: "snoop_default_mode"
    type: Enum
    scope: Public
    access: ReadWrite
    enum_values: "empty|disabled|filtered|full"
    prop_name: "persist.bluetooth.btsnoopdefaultmode"
}
```

关键字段如下：

| 字段 | 说明 |
|------|------|
| `module` | 生成代码的包名或命名空间 |
| `owner` | 属性所有者，例如 `Platform`、`Vendor`、`Odm` |
| `api_name` | 生成 API 的方法名 |
| `type` | 属性类型，例如 `Boolean`、`Integer`、`String`、`Enum` |
| `scope` | API 作用域，`Public` 或 `Internal` |
| `access` | 访问方式，`Readonly`、`Writeonce` 或 `ReadWrite` |
| `prop_name` | 真实系统属性名 |

### 6.6.3 `Android.bp` 模块定义

`sysprop_library` 在 Soong 中这样声明：

```json
sysprop_library {
    name: "PlatformProperties",
    srcs: ["srcs/android/sysprop/PlatformProperties.sysprop"],
    property_owner: "Platform",
}
```

构建系统会基于该模块生成 Java、C++ 和 Rust 访问库，并生成 API dump 文件进行兼容性检查。

### 6.6.4 代码生成过程

当定义一个 `sysprop_library` 模块时，Soong 会通过 `syspropLibraryHook` 自动创建多个子模块：

```go
// Source: build/soong/sysprop/sysprop_library.go
func syspropLibraryHook(ctx android.LoadHookContext, m *syspropLibrary) {
    ...
    // 1. C++ 实现库 (lib<name>)
    ctx.CreateModule(cc.LibraryFactory, &ccProps)

    // 2. Java 源码生成器
    ctx.CreateModule(syspropJavaGenFactory, &syspropGenProperties{
        Srcs:  m.properties.Srcs,
        Scope: scope,
        Name:  proptools.StringPtr(m.javaGenModuleName()),
    })

    // 3. Java 实现库
    ctx.CreateModule(java.LibraryFactory, &javaLibraryProperties{
        Name: proptools.StringPtr(m.BaseModuleName()),
        Srcs: []string{":" + m.javaGenModuleName()},
    })

    // 4. 公开 Java Stub（如果是平台所有且安装在 system 分区）
    if isOwnerPlatform && installedInSystem {
        ctx.CreateModule(syspropJavaGenFactory, ...)   // public scope
        ctx.CreateModule(java.LibraryFactory, ...)     // public stub
    }

    // 5. Rust 实现库
    ctx.CreateModule(syspropRustGenFactory, &rustProps)
    ...
}
```

```mermaid
graph TB
    SYSPROP[".sysprop 文件<br/>BluetoothProperties.sysprop"]

    subgraph "生成的模块"
        CC_LIB["C++ 库<br/>libPlatformProperties<br/>(cc_library)"]
        JAVA_GEN["Java 源码生成器<br/>PlatformProperties_java_gen<br/>(syspropJavaGenRule)"]
        JAVA_LIB["Java 库<br/>PlatformProperties<br/>(java_library)"]
        JAVA_PUB["Java 公开 Stub<br/>PlatformProperties_public<br/>(java_library)"]
        RUST_LIB["Rust 库<br/>libplatformproperties_rust<br/>(rust_library)"]
    end

    SYSPROP -->|"sysprop_cc"| CC_LIB
    SYSPROP -->|"sysprop_java"| JAVA_GEN
    JAVA_GEN -->|"srcjar"| JAVA_LIB
    SYSPROP -->|"sysprop_java (public scope)"| JAVA_PUB
    SYSPROP -->|"sysprop_rust"| RUST_LIB

    subgraph "API 管理"
        CURRENT["api/PlatformProperties-current.txt"]
        LATEST["api/PlatformProperties-latest.txt"]
        DUMP["API dump"]
        CHECK["API 兼容性检查"]
    end

    SYSPROP --> DUMP
    DUMP --> CHECK
    CHECK --> CURRENT
    CHECK --> LATEST

    style SYSPROP fill:#00b894,color:#fff
    style CC_LIB fill:#0984e3,color:#fff
    style JAVA_LIB fill:#e17055,color:#fff
    style RUST_LIB fill:#d63031,color:#fff
```

### 6.6.5 生成的 Java 代码

对于如下定义的属性：

```protobuf
prop {
    api_name: "snoop_default_mode"
    type: Enum
    scope: Public
    access: ReadWrite
    enum_values: "empty|disabled|filtered|full"
    prop_name: "persist.bluetooth.btsnoopdefaultmode"
}
```

生成的 Java 代码大致如下：

```java
package android.sysprop;

public final class BluetoothProperties {
    // 枚举类型
    public enum snoop_default_mode_values {
        EMPTY("empty"),
        DISABLED("disabled"),
        FILTERED("filtered"),
        FULL("full");
        ...
    }

    // Getter 方法
    public static Optional<snoop_default_mode_values> snoop_default_mode() {
        String value = SystemProperties.get("persist.bluetooth.btsnoopdefaultmode");
        return snoop_default_mode_values.tryParse(value);
    }

    // Setter 方法 (因为 access 为 ReadWrite)
    public static void snoop_default_mode(snoop_default_mode_values value) {
        SystemProperties.set("persist.bluetooth.btsnoopdefaultmode",
                              value.getPropValue());
    }
}
```

### 6.6.6 生成的 C++ 代码

对应的 C++ 代码会生成：

```cpp
namespace android::sysprop {

// 返回 std::optional 的 Getter
std::optional<std::string> snoop_default_mode();

// 返回 Result<void> 的 Setter
android::base::Result<void> snoop_default_mode(const std::string& value);

}  // namespace android::sysprop
```

### 6.6.7 生成代码中的 Scope 与 Access 控制

`scope` 字段控制生成的内容：

- **`Public`**：属性同时出现在 internal 和 public 生成库中。它被视为稳定 API，必须通过兼容性检查。
- **`Internal`**：属性仅出现在 internal 库中，不属于稳定 API 表面。

`access` 字段控制生成的方法：

- **`Readonly`**：仅生成 getter。此类属性通常不以 `persist.` 开头，且在构建期或启动时设置。
- **`Writeonce`**：同时生成 getter 和 setter，但 setter 文档说明其为一次性使用（用于 `ro.*` 属性）。
- **`ReadWrite`**：同时生成 getter 和 setter。

### 6.6.8 API 兼容性检查

`sysprop_library` 模块通过双文件检查机制强制执行 API 稳定性：

```go
// Source: build/soong/sysprop/sysprop_library.go
// 1. 从 .sysprop 文件 dump 当前 API
rule.Command().
    BuiltTool("sysprop_api_dump").
    Output(m.dumpedApiFile).
    Inputs(srcs)

// 2. 将 dump 结果与签入的 current.txt 进行比较（必须一致）
rule.Command().
    Text("( cmp").Flag("-s").
    Input(m.dumpedApiFile).
    Text(currentApiArgument).
    Text("|| ( echo ...error... ; exit 38) )")

// 3. 将 current.txt 与 latest.txt 进行比较（必须兼容）
rule.Command().
    BuiltTool("sysprop_api_checker").
    Text(latestApiArgument).
    Text(currentApiArgument)
```

这确保了：

1. `.sysprop` 文件与签入的 `api/<name>-current.txt` 匹配。
2. 当前 API 与 `api/<name>-latest.txt` 保持向后兼容。

在进行有意的 API 更改后更新 API：

```bash
m PlatformProperties-dump-api && \
    cp out/.../api-dump.txt <module>/api/PlatformProperties-current.txt
```

### 6.6.9 与 `property_contexts` 集成

`sysprop_library` 模块会自动与属性类型检查系统集成。所有 sysprop 库的列表在构建时被收集：

```go
// Source: build/soong/sysprop/sysprop_library.go
if m.ExportedToMake() {
    syspropLibrariesLock.Lock()
    defer syspropLibrariesLock.Unlock()

    libraries := syspropLibraries(ctx.Config())
    *libraries = append(*libraries, "//"+ctx.ModuleDir()+":"+ctx.ModuleName())
}
```

该列表由 `property_contexts` 构建规则使用，以确保 `property_contexts` 中的类型约束与 `.sysprop` 文件中声明的约束一致。

---

## 6.7 Vendor 属性与 Treble 隔离

### 6.7.1 Vendor Interface 与属性命名空间

Project Treble 引入了 system 分区和 vendor 分区之间的严格隔离。对应到系统属性，含义如下：

1. **Vendor 属性应使用 `vendor.` 或 `persist.vendor.` 前缀。** 这能明确它们位于 vendor 命名空间。
2. **系统组件不应依赖 vendor 专用属性。** `sysprop_library` 的 ownership 模型会在构建期执行该规则。
3. **暴露给 vendor 代码的平台属性必须稳定。** 当 vendor 代码使用 Platform 所有的 `sysprop_library` 时，只能访问 `Public` scope 属性，并且这些属性必须通过 API 兼容性检查。

### 6.7.2 Vendor Property Contexts

vendor 分区通过 `/vendor/etc/selinux/vendor_property_contexts` 提供自己的 property_contexts 文件。该文件定义 vendor 专用属性的 SELinux label。

从 vendor 分区文件加载属性时，property service 会使用特殊 vendor context：

```c
static constexpr const char* const kVendorPathPrefixes[4] = {
    "/vendor", "/odm", "/vendor_dlkm", "/odm_dlkm",
};

if (SelinuxGetVendorAndroidVersion() >= __ANDROID_API_P__) {
    for (const auto& vendor_path_prefix : kVendorPathPrefixes) {
        if (StartsWith(filename, vendor_path_prefix)) {
            context = kVendorContext;
        }
    }
}
```

这意味着从 vendor 分区文件加载的属性会以 vendor SELinux context 设置，其访问规则不同于 platform/init context。

### 6.7.3 Vendor API 级别

`ro.vendor.api_level` 属性由 init 自动计算，反映了 vendor 分区必须支持的最低 API 级别：

```c
// Source: system/core/init/property_service.cpp
static void property_initialize_ro_vendor_api_level() {
    constexpr auto VENDOR_API_LEVEL_PROP = "ro.vendor.api_level";

    if (__system_property_find(VENDOR_API_LEVEL_PROP) != nullptr) {
        return;  // 已显式设置
    }

    auto vendor_api_level = GetIntProperty("ro.board.first_api_level",
                                            __ANDROID_VENDOR_API_MAX__);
    if (vendor_api_level != __ANDROID_VENDOR_API_MAX__) {
        vendor_api_level = GetIntProperty("ro.board.api_level", vendor_api_level);
    }

    auto product_first_api_level =
        GetIntProperty("ro.product.first_api_level", __ANDROID_API_FUTURE__);
    if (product_first_api_level == __ANDROID_API_FUTURE__) {
        product_first_api_level =
            GetIntProperty("ro.build.version.sdk", __ANDROID_API_FUTURE__);
    }

    vendor_api_level = std::min(
        AVendorSupport_getVendorApiLevelOf(product_first_api_level),
        vendor_api_level);

    std::string error;
    PropertySetNoSocket(VENDOR_API_LEVEL_PROP,
                         std::to_string(vendor_api_level), &error);
}
```

### 6.7.4 跨分区属性访问规则

`sysprop_library` 构建系统根据所有权和安装分区强制执行访问规则：

```mermaid
graph LR
    subgraph "属性所有者"
        PO_PLATFORM["Platform (平台)"]
        PO_VENDOR["Vendor (厂商)"]
        PO_ODM["Odm (原始设计制造商)"]
    end

    subgraph "消费者分区"
        CP_SYSTEM["system / system_ext"]
        CP_VENDOR["vendor / odm"]
        CP_PRODUCT["product"]
    end

    PO_PLATFORM -->|"Public scope"| CP_SYSTEM
    PO_PLATFORM -->|"Public scope"| CP_VENDOR
    PO_PLATFORM -->|"Public scope"| CP_PRODUCT

    PO_VENDOR -->|"Internal scope"| CP_VENDOR
    PO_VENDOR -.->|"拒绝访问"| CP_SYSTEM
    PO_VENDOR -->|"Public scope"| CP_PRODUCT

    PO_ODM -->|"Internal scope"| CP_VENDOR
    PO_ODM -.->|"拒绝访问"| CP_SYSTEM
    PO_ODM -.->|"拒绝访问"| CP_PRODUCT

    style PO_PLATFORM fill:#00b894,color:#fff
    style PO_VENDOR fill:#e17055,color:#fff
    style PO_ODM fill:#d63031,color:#fff
```

核心规则如下：

- **平台所有（Platform-owned）** 的属性可以被所有分区使用 `Public` 作用域读取。
- **厂商所有（Vendor-owned）** 的属性无法从系统（system）分区访问。
- **ODM 所有（ODM-owned）** 的属性只能从 vendor/ODM 分区访问。
- **产品（Product）** 分区始终使用 `Public` 作用域，因为它不能拥有属性。

### 6.7.5 ODM 与 Vendor DLKM 分区

ODM（Original Design Manufacturer）和 DLKM（Dynamic Loadable Kernel Modules）分区拥有由属性服务加载的专属 `build.prop` 文件。加载顺序确保了 ODM 属性可以覆盖厂商属性：

```text
vendor/default.prop       -> 首先加载
vendor/build.prop         -> 覆盖 vendor/default.prop
vendor_dlkm/etc/build.prop
odm_dlkm/etc/build.prop
odm/etc/build.prop        -> 覆盖所有 vendor 属性
```

这种层级结构允许 ODM 在不修改 vendor 分区的情况下定制厂商属性。

---

## 6.8 启动属性

### 6.8.1 构建属性（`ro.build.*`）

构建属性由构建系统在构建期设置，并嵌入在 `build.prop` 文件中。它们描述了构建配置：

| 属性 | 说明 | 示例 |
|----------|-------------|---------|
| `ro.build.display.id` | 构建的显示字符串 | `UP1A.231005.007` |
| `ro.build.version.incremental` | 增量构建号 | `10817346` |
| `ro.build.version.sdk` | SDK API 级别 | `34` |
| `ro.build.version.release` | 用户可见版本 | `14` |
| `ro.build.version.security_patch` | 安全补丁日期 | `2023-10-05` |
| `ro.build.type` | 构建类型 | `user` / `userdebug` / `eng` |
| `ro.build.tags` | 构建标签 | `release-keys` / `dev-keys` |
| `ro.build.fingerprint` | 复合指纹（Fingerprint） | （自动派生） |
| `ro.build.id` | 构建 ID | `UP1A.231005.007` |

### 6.8.2 Build Fingerprint 派生过程

如果未显式设置 `ro.build.fingerprint`，init 会自动对其进行派生：

```c
// Source: system/core/init/property_service.cpp
static void property_derive_build_fingerprint() {
    std::string build_fingerprint = GetProperty("ro.build.fingerprint", "");
    if (!build_fingerprint.empty()) {
        return;  // 已显式设置
    }

    const std::string UNKNOWN = "unknown";
    build_fingerprint = GetProperty("ro.product.brand", UNKNOWN);
    build_fingerprint += '/';
    build_fingerprint += GetProperty("ro.product.name", UNKNOWN);

    // 支持 16KB 页大小设备选项
    bool has16KbDevOption =
        android::base::GetBoolProperty("ro.product.build.16k_page.enabled", false);
    if (has16KbDevOption && getpagesize() == 16384) {
        build_fingerprint += "_16kb";
    }

    build_fingerprint += '/';
    build_fingerprint += GetProperty("ro.product.device", UNKNOWN);
    build_fingerprint += ':';
    build_fingerprint += GetProperty("ro.build.version.release_or_codename", UNKNOWN);
    build_fingerprint += '/';
    build_fingerprint += GetProperty("ro.build.id", UNKNOWN);
    build_fingerprint += '/';
    build_fingerprint += GetProperty("ro.build.version.incremental", UNKNOWN);
    build_fingerprint += ':';
    build_fingerprint += GetProperty("ro.build.type", UNKNOWN);
    build_fingerprint += '/';
    build_fingerprint += GetProperty("ro.build.tags", UNKNOWN);

    PropertySetNoSocket("ro.build.fingerprint", build_fingerprint, &error);
}
```

生成的指纹示例如下：
`google/raven/raven:14/UP1A.231005.007/10817346:userdebug/dev-keys`

### 6.8.3 产品属性（`ro.product.*`）

产品属性描述了设备的身份。它们遵循一套基于分区的派生系统，每个分区都可以定义自己的值，并由一套优先级顺序决定最终胜出的值：

```c
// Source: system/core/init/property_service.cpp
static void property_initialize_ro_product_props() {
    const char* RO_PRODUCT_PROPS[] = {
        "brand", "device", "manufacturer", "model", "name",
    };
    const char* RO_PRODUCT_PROPS_DEFAULT_SOURCE_ORDER =
        "product,odm,vendor,system_ext,system";

    std::string ro_product_props_source_order =
        GetProperty("ro.product.property_source_order", "");
    if (ro_product_props_source_order.empty()) {
        ro_product_props_source_order = RO_PRODUCT_PROPS_DEFAULT_SOURCE_ORDER;
    }

    for (const auto& ro_product_prop : RO_PRODUCT_PROPS) {
        std::string base_prop = "ro.product." + std::string(ro_product_prop);
        if (!GetProperty(base_prop, "").empty()) continue;

        for (const auto& source : Split(ro_product_props_source_order, ",")) {
            std::string target_prop = "ro.product." + source + "." + ro_product_prop;
            std::string target_prop_val = GetProperty(target_prop, "");
            if (!target_prop_val.empty()) {
                PropertySetNoSocket(base_prop, target_prop_val, &error);
                break;
            }
        }
    }
}
```

`ro.product.model` 的派生链如下：

```mermaid
graph LR
    A["ro.product.product.model<br/>(product 分区)"] -->|"最高优先级"| RESULT["ro.product.model"]
    B["ro.product.odm.model<br/>(odm 分区)"] -->|"如果 product 为空"| RESULT
    C["ro.product.vendor.model<br/>(vendor 分区)"] -->|"如果 odm 为空"| RESULT
    D["ro.product.system_ext.model<br/>(system_ext 分区)"] -->|"如果 vendor 为空"| RESULT
    E["ro.product.system.model<br/>(system 分区)"] -->|"最低优先级"| RESULT

    style RESULT fill:#00b894,color:#fff
```

### 6.8.4 硬件属性（`ro.hardware.*`）

硬件属性描述了物理硬件平台：

| 属性 | 来源 | 说明 |
|----------|--------|-------------|
| `ro.hardware` | 内核命令行 / DT | 硬件平台名称 |
| `ro.boot.hardware` | 内核命令行 | 启动硬件标识符 |
| `ro.hardware.chipname` | Vendor build.prop | SoC 芯片名称 |
| `ro.boot.hardware.cpu.pagesize` | 启动时派生 | CPU 页大小 |

硬件属性通常从内核命令行设置，然后进行传播：

```c
// 来自 ExportKernelBootProps():
{ "ro.boot.hardware", "ro.hardware", "unknown" }
```

CPU 页大小属性是自动派生的：

```c
// Source: system/core/init/property_service.cpp
void PropertyLoadDerivedDefaults() {
    const char* PAGE_PROP = "ro.boot.hardware.cpu.pagesize";
    if (GetProperty(PAGE_PROP, "").empty()) {
        PropertySetNoSocket(PAGE_PROP, std::to_string(getpagesize()), &error);
    }
}
```

### 6.8.5 启动模式属性（`ro.boot.*`）

这些属性来自内核命令行（`androidboot.*`）和 bootconfig：

| 属性 | 说明 |
|----------|-------------|
| `ro.boot.serialno` | 设备序列号 |
| `ro.boot.mode` | 启动模式 (normal, charger, recovery) |
| `ro.boot.baseband` | 基带版本 |
| `ro.boot.bootloader` | Bootloader 版本 |
| `ro.boot.hardware` | 硬件标识符 |
| `ro.boot.revision` | 硬件修订版本 |
| `ro.boot.slot_suffix` | A/B 槽位后缀 (_a 或 _b) |
| `ro.boot.verifiedbootstate` | 验证启动状态 (green/yellow/orange) |

内核命令行到属性的映射：

```text
内核命令行:  androidboot.serialno=ABC123
    -> 属性:  ro.boot.serialno=ABC123

Bootconfig:      androidboot.hardware=tensor
    -> 属性:  ro.boot.hardware=tensor
```

### 6.8.6 CPU ABI 列表属性

CPU ABI 列表属性决定了设备支持哪些指令集架构：

```c
// Source: system/core/init/property_service.cpp
static void property_initialize_ro_cpu_abilist() {
    const char* kAbilistSources[] = {
        "product", "odm", "vendor", "system",
    };

    // 查找第一个定义了这些属性的来源
    for (const auto& source : kAbilistSources) {
        const auto abilist32_prop = "ro." + source + ".product.cpu.abilist32";
        const auto abilist64_prop = "ro." + source + ".product.cpu.abilist64";
        abilist32_prop_val = GetProperty(abilist32_prop, "");
        abilist64_prop_val = GetProperty(abilist64_prop, "");
        if (abilist32_prop_val != "" || abilist64_prop_val != "") {
            break;
        }
    }

    // 合并：64 位优先，然后是 32 位
    auto abilist_prop_val = abilist64_prop_val;
    if (abilist32_prop_val != "") {
        if (abilist_prop_val != "") abilist_prop_val += ",";
        abilist_prop_val += abilist32_prop_val;
    }

    PropertySetNoSocket("ro.product.cpu.abilist", abilist_prop_val, &error);
    PropertySetNoSocket("ro.product.cpu.abilist32", abilist32_prop_val, &error);
    PropertySetNoSocket("ro.product.cpu.abilist64", abilist64_prop_val, &error);
}
```

典型值：

- `ro.product.cpu.abilist` = `arm64-v8a,armeabi-v7a,armeabi`
- `ro.product.cpu.abilist64` = `arm64-v8a`
- `ro.product.cpu.abilist32` = `armeabi-v7a,armeabi`

### 6.8.7 完整启动属性加载时间线

```mermaid
sequenceDiagram
    participant KER as 内核
    participant IN1 as init (第一阶段)
    participant IN2 as init (第二阶段)
    participant PS as PropertyService
    participant DATA as /data 分区

    Note over KER: 启动开始
    KER->>IN1: exec /init (PID 1)
    IN1->>IN2: exec 第二阶段 init

    Note over IN2: PropertyInit()
    IN2->>IN2: mkdir /dev/__properties__
    IN2->>IN2: CreateSerializedPropertyInfo()
    IN2->>IN2: __system_property_area_init()

    Note over IN2: 加载内核属性
    IN2->>IN2: ProcessKernelDt() -> ro.boot.*
    IN2->>IN2: ProcessBootconfig() -> ro.boot.*
    IN2->>IN2: ProcessKernelCmdline() -> ro.boot.*
    IN2->>IN2: ExportKernelBootProps() -> ro.serialno, ro.hardware, ...

    Note over IN2: 加载分区属性
    IN2->>IN2: /system/build.prop
    IN2->>IN2: /system_ext/etc/build.prop
    IN2->>IN2: /vendor/build.prop
    IN2->>IN2: /odm/etc/build.prop
    IN2->>IN2: /product/etc/build.prop

    Note over IN2: 派生计算属性
    IN2->>IN2: property_initialize_ro_product_props()
    IN2->>IN2: property_derive_build_fingerprint()
    IN2->>IN2: property_initialize_ro_cpu_abilist()
    IN2->>IN2: property_initialize_ro_vendor_api_level()

    Note over PS: StartPropertyService()
    IN2->>PS: 创建 property_service socket
    PS->>PS: 启动 epoll 线程

    Note over DATA: /data 已挂载
    IN2->>PS: kLoadPersistentProperties
    PS->>DATA: LoadPersistentProperties()
    DATA-->>PS: persist.* 属性
    PS->>PS: InitPropertySet("ro.persistent_properties.ready", "true")

    Note over PS: 系统完全启动
    PS->>PS: sys.boot_completed = 1
```

---

## 6.9 动手实践：探索系统属性

本节提供了用于理解系统属性机制的手操练习。所有练习均假设你拥有一台通过 `adb` 连接、运行 `userdebug` 或 `eng` 构建版本的设备或模拟器。

### 6.9.1 练习：列出并检查属性

**列出所有属性：**

```bash
# 列出所有属性（在真实设备上通常有 800-1200 个）
adb shell getprop | wc -l

# 列出所有只读属性
adb shell getprop | grep "^\[ro\."

# 列出所有持久化属性
adb shell getprop | grep "^\[persist\."
```

**读取特定属性：**

```bash
# 构建指纹
adb shell getprop ro.build.fingerprint

# 设备型号
adb shell getprop ro.product.model

# API 级别
adb shell getprop ro.build.version.sdk

# 启动模式
adb shell getprop ro.bootmode

# 检查设备是否可调试
adb shell getprop ro.debuggable
```

**检查属性区域文件：**

```bash
# 列出属性区域文件
adb shell ls -la /dev/__properties__/

# 检查 property_info 文件大小
adb shell ls -la /dev/__properties__/property_info

# 统计属性区域文件的数量（每个 SELinux 上下文一个）
adb shell ls /dev/__properties__/ | wc -l
```

### 6.9.2 练习：设置并观察属性

**设置调试属性：**

```bash
# 设置调试属性（在 userdebug 构建上允许 shell 用户操作）
adb shell setprop debug.mytest.value "hello world"

# 验证是否已设置
adb shell getprop debug.mytest.value
# 输出: hello world

# 尝试设置持久化属性
adb shell setprop persist.mytest.value "survives reboot"
adb shell getprop persist.mytest.value

# 重启并验证持久性
adb reboot
# 重启后：
adb shell getprop persist.mytest.value
# 输出: survives reboot
```

**观察只读约束：**

```bash
# 尝试更改只读属性（将会失败）
adb shell setprop ro.build.type "eng"
# 此时会静默失败或产生错误

# 验证其未发生变化
adb shell getprop ro.build.type
```

### 6.9.3 练习：观察属性变化

**使用 waitforprop 等待属性：**

```bash
# 在一个终端中，等待属性发生变化
adb shell "
    echo 'Waiting for debug.mytest.signal...'
    while [ \"\$(getprop debug.mytest.signal)\" != 'go' ]; do
        sleep 0.1
    done
    echo 'Signal received!'
"

# 在另一个终端中，触发该变化
adb shell setprop debug.mytest.signal go
```

**使用 watchprops 监控所有属性变化：**

```bash
# 开始监控（此工具会阻塞并打印实时发生的更改）
adb shell watchprops
# 随后在另一个终端中设置任何属性，即可看到报告
```

### 6.9.4 练习：检查属性上下文（Property Contexts）

**查看 property_contexts 文件：**

```bash
# 平台属性上下文
adb shell cat /system/etc/selinux/plat_property_contexts | head -30

# 厂商属性上下文
adb shell cat /vendor/etc/selinux/vendor_property_contexts | head -20

# 检查特定属性拥有的上下文
adb shell getprop -Z debug.test.value
```

**测试 SELinux 强制执行：**

```bash
# 检查你的 shell 所处的 SELinux 上下文
adb shell id -Z

# 尝试设置一个你没有权限访问的属性
adb shell setprop ro.boot.serialno "fake"
# 由于只读限制和 SELinux 限制，此操作应当失败

# 检查审核日志（audit log）中的拒绝信息
adb shell dmesg | grep "avc.*property_service"
```

### 6.9.5 练习：持久化属性存储

**检查持久化属性文件：**

```bash
# 检查持久化属性文件
adb shell ls -la /data/property/

# 该文件经由 protobuf 编码，无法直接阅读
# 你可以使用十六进制转储（hex dump）进行查看
adb shell xxd /data/property/persistent_properties | head -20
```

**追踪持久化属性的写入：**

```bash
# 设置持久化属性并观察文件的更新
adb shell "
    ls -la /data/property/persistent_properties
    setprop persist.mytest.timestamp \$(date +%s)
    ls -la /data/property/persistent_properties
"
# 文件大小和修改时间应当会发生变化
```

### 6.9.6 练习：属性派生链

**追踪产品属性的派生：**

```bash
# 查看 ro.product.model 的来源
# 检查每个来源分区：
echo "System:     $(adb shell getprop ro.product.system.model)"
echo "System_ext: $(adb shell getprop ro.product.system_ext.model)"
echo "Vendor:     $(adb shell getprop ro.product.vendor.model)"
echo "ODM:        $(adb shell getprop ro.product.odm.model)"
echo "Product:    $(adb shell getprop ro.product.product.model)"
echo ""
echo "Final:      $(adb shell getprop ro.product.model)"
echo "Source order: $(adb shell getprop ro.product.property_source_order)"
```

**检查构建指纹（Build Fingerprint）的组成部分：**

```bash
echo "Brand:   $(adb shell getprop ro.product.brand)"
echo "Name:    $(adb shell getprop ro.product.name)"
echo "Device:  $(adb shell getprop ro.product.device)"
echo "Release: $(adb shell getprop ro.build.version.release_or_codename)"
echo "ID:      $(adb shell getprop ro.build.id)"
echo "Incr:    $(adb shell getprop ro.build.version.incremental)"
echo "Type:    $(adb shell getprop ro.build.type)"
echo "Tags:    $(adb shell getprop ro.build.tags)"
echo ""
echo "Fingerprint: $(adb shell getprop ro.build.fingerprint)"
```

### 6.9.7 练习：通过属性控制服务

**使用 ctl.* 属性控制服务：**

```bash
# 列出正在运行的服务
adb shell getprop | grep "init.svc\." | grep running

# 检查特定服务的状态
adb shell getprop init.svc.adbd

# 通过 ctl 属性重启服务（需要相应权限）
adb root
adb shell setprop ctl.restart adbd

# 观察服务状态的变化
adb shell "
    echo 'Before: '$(getprop init.svc.adbd)
    setprop ctl.restart adbd
    sleep 1
    echo 'After:  '$(getprop init.svc.adbd)
"
```

### 6.9.8 练习：构建 sysprop_library

**创建一个极简的 sysprop_library：**

创建一个 `.sysprop` 文件：

```protobuf
# my_module/MyAppProperties.sysprop
module: "com.example.MyAppProperties"
owner: Platform

prop {
    api_name: "debug_enabled"
    type: Boolean
    scope: Internal
    access: ReadWrite
    prop_name: "persist.myapp.debug_enabled"
}

prop {
    api_name: "max_connections"
    type: Integer
    scope: Internal
    access: ReadWrite
    prop_name: "persist.myapp.max_connections"
}
```

创建 `Android.bp`：

```json
sysprop_library {
    name: "MyAppProperties",
    srcs: ["MyAppProperties.sysprop"],
    property_owner: "Platform",
}
```

构建完成后，生成的库将提供类型安全的访问方式：

```java
// 生成的 Java 用法
import com.example.MyAppProperties;

// 类型安全的布尔值 Getter (返回 Optional<Boolean>)
Optional<Boolean> debug = MyAppProperties.debug_enabled();
if (debug.orElse(false)) {
    Log.d(TAG, "Debug mode is enabled");
}

// 类型安全的整数 Getter
Optional<Integer> maxConn = MyAppProperties.max_connections();
int connections = maxConn.orElse(10);

// 类型安全的 Setter
MyAppProperties.debug_enabled(true);
MyAppProperties.max_connections(20);
```

### 6.9.9 练习：测量属性读取性能

**基准测试属性读取：**

```bash
# 计时 10000 次属性读取
adb shell "
    START=\$(date +%s%N)
    for i in \$(seq 1 10000); do
        getprop ro.build.fingerprint > /dev/null
    done
    END=\$(date +%s%N)
    ELAPSED=\$(( (END - START) / 1000000 ))
    echo \"10000 reads in \${ELAPSED}ms\"
    echo \"Average: \$(( ELAPSED * 1000 / 10000 )) us per read\"
"
```

请注意，`getprop` 涉及进程创建的开销。实际的共享内存查找速度要快得多（通常在 1 微秒以下）。更准确的基准测试应当使用一个直接调用 `__system_property_find()` 和 `__system_property_read_callback()` 的 native 程序。

### 6.9.10 练习：在内存中探索属性前缀树（Trie）

**使用 debuggerd 检查属性内存映射：**

```bash
# 查找 init 进程
adb shell "cat /proc/1/maps | grep __properties__"
# 这将显示 init 的内存映射属性区域

# 对于任何其他进程，将 1 替换为 PID：
PID=$(adb shell pidof com.android.systemui)
adb shell "cat /proc/$PID/maps | grep __properties__"
```

此练习揭示了每个进程虽然可能在不同的虚拟地址映射属性区域，但它们都通过共享内存映射文件引用了同一批物理页。

---

## 总结

Android 的系统属性是一个看似简单的机制，但在其键值接口之下隐藏了相当大的复杂性。该架构通过几个相互协作的子系统实现了其设计目标：

1. **无锁读取**：通过内存映射文件和基于前缀树（trie）的查找结构实现，利用原子操作和“脏数据备份协议”在不使用锁的情况下确保一致性。

2. **集中写入**：通过 init 的 property service 进行，它通过 Unix domain socket 接收请求，并调解对共享内存的所有更改。

3. **SELinux 强制执行**：通过按上下文划分的属性区域文件实现，其中每个 SELinux 上下文都拥有自己的内存映射文件，并由内核强制执行访问控制。

4. **类型化、受 API 管理的属性**：通过 `sysprop_library` 构建系统模块实现，该模块在 Java、C++ 和 Rust 中生成类型安全的访问器，同时强制执行 API 兼容性。

5. **分区隔离**：通过与 Treble 对齐的所有权模型实现，其中平台（platform）、厂商（vendor）和 ODM 属性具有明确定义的边界和访问规则。

系统属性的核心源文件包括：

| 组件 | 路径 |
|-----------|------|
| 属性服务 (init) | `system/core/init/property_service.cpp` |
| 持久化属性 | `system/core/init/persistent_properties.cpp` |
| 共享内存前缀树 | `bionic/libc/system_properties/prop_area.cpp` |
| prop_info 结构 | `bionic/libc/system_properties/include/system_properties/prop_info.h` |
| 前缀树节点结构 | `bionic/libc/system_properties/include/system_properties/prop_area.h` |
| 系统属性核心 | `bionic/libc/system_properties/system_properties.cpp` |
| NDK API | `bionic/libc/bionic/system_property_api.cpp` |
| 序列化上下文 | `bionic/libc/system_properties/contexts_serialized.cpp` |
| 属性信息前缀树 | `system/core/property_service/libpropertyinfoparser/include/property_info_parser/property_info_parser.h` |
| Java API | `frameworks/base/core/java/android/os/SystemProperties.java` |
| Soong sysprop_library | `build/soong/sysprop/sysprop_library.go` |
| 平台属性上下文 | `system/sepolicy/private/property_contexts` |
| 示例 .sysprop 文件 | `system/libsysprop/srcs/android/sysprop/BluetoothProperties.sysprop` |
