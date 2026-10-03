/**
 * Navegação do app.
 *
 * Cinco abas embaixo, e não sete: com sete, cada uma fica com dois centímetros
 * de largura e um rótulo que ninguém lê. Embaixo fica o que se olha toda semana
 * - incluindo "Lançar", que é diário e por isso não podia estar escondido. O que
 * se usa uma vez por mês ou por ano vira uma tela empilhada, aberta pela aba
 * "Mais".
 */

import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { DarkTheme, NavigationContainer, useNavigation } from '@react-navigation/native';
import {
  createNativeStackNavigator,
  type NativeStackNavigationProp,
} from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { AccountsScreen } from '@/screens/AccountsScreen';
import { DashboardScreen } from '@/screens/DashboardScreen';
import { EntryScreen } from '@/screens/EntryScreen';
import { ExpensesScreen } from '@/screens/ExpensesScreen';
import { ForecastScreen } from '@/screens/ForecastScreen';
import { ImportScreen } from '@/screens/ImportScreen';
import { InvestmentsScreen } from '@/screens/InvestmentsScreen';
import { MoreScreen } from '@/screens/MoreScreen';
import { TaxScreen } from '@/screens/TaxScreen';
import { colors, typography } from '@/theme';

type StackParams = {
  Abas: undefined;
  Contas: undefined;
  Importar: undefined;
  Investimentos: undefined;
  IR: undefined;
};

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator<StackParams>();

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

/** Ícone tipográfico: sem dependência de pacote de ícones no bootstrap. */
function TabIcon({ label, focused }: { label: string; focused: boolean }): React.ReactElement {
  return (
    <View style={styles.icon}>
      <Text style={[styles.iconText, focused && { color: colors.red }]}>{label}</Text>
    </View>
  );
}

/** A aba "Mais" é um índice: quem navega é o empilhado, não ela. */
function MoreTab(): React.ReactElement {
  const navigation = useNavigation<NativeStackNavigationProp<StackParams>>();
  return <MoreScreen aoEscolher={(destino) => navigation.navigate(destino)} />;
}

function Abas(): React.ReactElement {
  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerTitleStyle: { color: colors.text, fontSize: 21, fontWeight: '700' },
        headerShadowVisible: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          height: 66,
          paddingTop: 6,
          paddingBottom: 8,
        },
        tabBarLabelStyle: { fontSize: 12, fontWeight: '600' },
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
        name="Lancar"
        component={EntryScreen}
        options={{
          title: 'Lançar',
          tabBarLabel: 'Lançar',
          tabBarIcon: ({ focused }) => <TabIcon label="＋" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Gastos"
        component={ExpensesScreen}
        options={{ tabBarIcon: ({ focused }) => <TabIcon label="≡" focused={focused} /> }}
      />
      <Tab.Screen
        name="Previsoes"
        component={ForecastScreen}
        options={{
          title: 'Previsões',
          tabBarLabel: 'Previsões',
          tabBarIcon: ({ focused }) => <TabIcon label="◎" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Mais"
        component={MoreTab}
        options={{ tabBarIcon: ({ focused }) => <TabIcon label="⋯" focused={focused} /> }}
      />
    </Tab.Navigator>
  );
}

export function RootNavigator(): React.ReactElement {
  return (
    <NavigationContainer theme={navigationTheme}>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: colors.background },
          headerTitleStyle: { color: colors.text, fontSize: 21, fontWeight: '700' },
          headerTintColor: colors.red,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="Abas" component={Abas} options={{ headerShown: false }} />
        <Stack.Screen
          name="Contas"
          component={AccountsScreen}
          options={{ title: 'Contas e cartões' }}
        />
        <Stack.Screen
          name="Importar"
          component={ImportScreen}
          options={{ title: 'Importar extrato' }}
        />
        <Stack.Screen name="Investimentos" component={InvestmentsScreen} />
        <Stack.Screen name="IR" component={TaxScreen} options={{ title: 'Imposto de Renda' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  icon: { alignItems: 'center', justifyContent: 'center' },
  iconText: { fontSize: 20, color: colors.textFaint },
});
