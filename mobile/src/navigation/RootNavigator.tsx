/** Abas do app, uma por modulo do sistema. */

import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { DarkTheme, NavigationContainer } from '@react-navigation/native';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { DashboardScreen } from '@/screens/DashboardScreen';
import { ExpensesScreen } from '@/screens/ExpensesScreen';
import { ForecastScreen } from '@/screens/ForecastScreen';
import { ImportScreen } from '@/screens/ImportScreen';
import { InvestmentsScreen } from '@/screens/InvestmentsScreen';
import { TaxScreen } from '@/screens/TaxScreen';
import { colors, typography } from '@/theme';

const Tab = createBottomTabNavigator();

const navigationTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    border: colors.border,
    text: colors.text,
    primary: colors.red,
  },
};

/** Icone tipografico: sem dependencia de pacote de icones no bootstrap. */
function TabIcon({ label, focused }: { label: string; focused: boolean }): React.ReactElement {
  return (
    <View style={styles.icon}>
      <Text style={[styles.iconText, focused && { color: colors.red }]}>{label}</Text>
    </View>
  );
}

export function RootNavigator(): React.ReactElement {
  return (
    <NavigationContainer theme={navigationTheme}>
      <Tab.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: colors.background },
          headerTitleStyle: { color: colors.text, ...typography.title },
          headerShadowVisible: false,
          tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
          tabBarActiveTintColor: colors.red,
          tabBarInactiveTintColor: colors.textFaint,
        }}
      >
        <Tab.Screen
          name="Dashboard"
          component={DashboardScreen}
          options={{
            title: 'Resumo',
            tabBarIcon: ({ focused }) => <TabIcon label="◱" focused={focused} />,
          }}
        />
        <Tab.Screen
          name="Gastos"
          component={ExpensesScreen}
          options={{ tabBarIcon: ({ focused }) => <TabIcon label="≡" focused={focused} /> }}
        />
        <Tab.Screen
          name="Importar"
          component={ImportScreen}
          options={{
            title: 'Importar extrato',
            tabBarIcon: ({ focused }) => <TabIcon label="↥" focused={focused} />,
          }}
        />
        <Tab.Screen
          name="Previsoes"
          component={ForecastScreen}
          options={{
            title: 'Previsões',
            tabBarIcon: ({ focused }) => <TabIcon label="◎" focused={focused} />,
          }}
        />
        <Tab.Screen
          name="Investimentos"
          component={InvestmentsScreen}
          options={{ tabBarIcon: ({ focused }) => <TabIcon label="◈" focused={focused} /> }}
        />
        <Tab.Screen
          name="IR"
          component={TaxScreen}
          options={{
            title: 'Imposto de Renda',
            tabBarIcon: ({ focused }) => <TabIcon label="%" focused={focused} />,
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  icon: { alignItems: 'center', justifyContent: 'center' },
  iconText: { fontSize: 18, color: colors.textFaint },
});
