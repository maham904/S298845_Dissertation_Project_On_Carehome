import SwiftUI

struct ContentView: View {
    @State private var username = ""
    @State private var password = ""
    @State private var message = ""

    var body: some View {
        VStack(spacing: 20) {

            Text("CareHome Login")
                .font(.largeTitle)
                .bold()

            TextField("Username", text: $username)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .autocapitalization(.none)

            SecureField("Password", text: $password)
                .textFieldStyle(RoundedBorderTextFieldStyle())

            Button("Login") {
                login()
            }
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(8)

            Text(message)
                .foregroundColor(.red)
        }
        .padding()
    }

    func login() {
        AuthService.login(username: username, password: password) { result in
            DispatchQueue.main.async {
                switch result {
                case .success:
                    message = "Login Successful"
                case .failure(let error):
                    message = error.localizedDescription
                }
            }
        }
    }
}

