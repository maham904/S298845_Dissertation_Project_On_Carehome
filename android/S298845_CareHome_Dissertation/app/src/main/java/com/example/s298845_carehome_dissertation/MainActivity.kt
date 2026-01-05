package com.example.s298845_carehome_dissertation

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val email = findViewById<EditText>(R.id.emailEditText)
        val password = findViewById<EditText>(R.id.passwordEditText)
        val button = findViewById<Button>(R.id.loginButton)
        val result = findViewById<TextView>(R.id.resultText)

        button.setOnClickListener {
            val userEmail = email.text.toString().trim()
            val userPassword = password.text.toString().trim()

            val req = LoginRequest(username = userEmail, password = userPassword)

            RetrofitClient.api.login(req).enqueue(object : Callback<LoginResponse> {
                override fun onResponse(call: Call<LoginResponse>, response: Response<LoginResponse>) {
                    if (response.isSuccessful && response.body() != null) {
                        val token = response.body()!!.access
                        TokenStorage.saveAccessToken(this@MainActivity, token)
                        result.text = "✅ Login Success"
                    } else {
                        result.text = "❌ Invalid credentials"
                    }
                }

                override fun onFailure(call: Call<LoginResponse>, t: Throwable) {
                    result.text = "❌ Network error: ${t.message}"
                }
            })
        }
    }
}
