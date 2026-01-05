//
//  TokenStorage.swift
//  CareHomeApp CareHomeApp CareHomeApp
//
//  Created by Maham Khan  on 04/01/2026.
//

import Foundation
import Security

class TokenStorage {

    static let key = "jwt_token"

    static func save(token: String) {
        let data = token.data(using: .utf8)!

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data
        ]

        SecItemDelete(query as CFDictionary)
        SecItemAdd(query as CFDictionary, nil)
    }

    static func get() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true
        ]

        var item: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &item)

        if status == errSecSuccess {
            if let data = item as? Data {
                return String(decoding: data, as: UTF8.self)
            }
        }
        return nil
    }
}
