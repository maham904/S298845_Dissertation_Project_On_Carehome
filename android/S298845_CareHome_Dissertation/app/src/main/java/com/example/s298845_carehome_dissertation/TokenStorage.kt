package com.example.s298845_carehome_dissertation

import android.content.Context
import androidx.core.content.edit

object TokenStorage {
    private const val PREFS = "auth_prefs"
    private const val KEY_ACCESS = "access_token"

    fun saveAccessToken(context: Context, token: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit {
                putString(KEY_ACCESS, token)
            }
    }

    fun getAccessToken(context: Context): String? {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_ACCESS, null)
    }
}
