//
//  AuthService.swift
//  CareHomeApp CareHomeApp CareHomeApp
//
//  Created by Maham Khan  on 04/01/2026.
//

import Foundation

class AuthService {

    static func login(
        username: String,
        password: String,
        completion: @escaping (Result<Void, Error>) -> Void
    ) {

        guard let url = URL(
            string: "https://s298845-dissertation-project-on-carehome.onrender.com/api/token/"
        ) else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: String] = [
            "username": username,
            "password": password
        ]

        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, response, error in

            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(NSError()))
                return
            }

            do {
                let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

                if let access = json?["access"] as? String {
                    TokenStorage.save(token: access)
                    completion(.success(()))
                } else {
                    completion(.failure(NSError(domain: "Login failed", code: 401)))
                }
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}
