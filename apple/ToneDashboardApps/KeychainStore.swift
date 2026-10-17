import Foundation
import Security

enum KeychainStore {
    // Keep the legacy service; new account keys include HTTPS host, port and username.
    private static let service = "ovh.tonecas.embydashboard"
    @discardableResult static func savePassword(_ password: String, account: String) -> OSStatus {
        let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword, kSecAttrService as String:service, kSecAttrAccount as String:account]
        let update = [kSecValueData as String:Data(password.utf8)]
        let status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        if status != errSecItemNotFound { return status }
        var insert = query; insert[kSecValueData as String] = Data(password.utf8)
        insert[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        return SecItemAdd(insert as CFDictionary, nil)
    }
    static func password(account: String) -> String {
        let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword, kSecAttrService as String:service, kSecAttrAccount as String:account, kSecReturnData as String:true, kSecMatchLimit as String:kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return "" }
        return String(data:data,encoding:.utf8) ?? ""
    }
}
