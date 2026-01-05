package com.example.s298845_carehome_dissertation
import retrofit2.Call
import retrofit2.http.Body
import retrofit2.http.POST

interface ApiService {
    @POST("api/token/")
    fun login(@Body request: LoginRequest): Call<LoginResponse>
}
