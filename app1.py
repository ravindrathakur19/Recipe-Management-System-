import streamlit as st
import json
import os
from collections import deque
from google import genai  # 👈 new import

# --------------- GEMINI SETUP ---------------
# Reads GEMINI_API_KEY from Streamlit secrets (we will set during deployment)
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    client = None  # Will show a warning in UI if not configured

MODEL_NAME = "gemini-2.5-flash"


def ask_recipe_ai(prompt: str) -> str:
    """
    Call Gemini 2.5 Flash to generate a detailed recipe.
    Follows the same style as your first-aid bot example.
    """
    system_instruction = (
        "You are a helpful cooking assistant. "
        "You give clear, step-by-step recipes with ingredients and instructions. "
        "Be detailed but easy to follow. Assume the user is a beginner cook."
    )

    full_prompt = (
        f"{system_instruction}\n\n"
        f"User wants a recipe or help with cooking.\n"
        f"User: {prompt}\n"
        f"Assistant:"
    )

    if client is None:
        return (
            "Gemini API is not configured. "
            "On Streamlit Cloud, go to **Settings → Secrets** and add:\n\n"
            "`GEMINI_API_KEY = \"your-key\"`"
        )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt,
        )
        text = (response.text or "").strip()
        if not text:
            return "Sorry, I couldn't generate a response. Please try again."
        return text
    except Exception as e:
        return f"Error from AI: {e}"


# ================================
# Binary Search Tree for Recipes
# ================================

class TreeNode:
    def __init__(self, recipe):
        self.recipe = recipe
        self.left = None
        self.right = None


class BinarySearchTree:
    def __init__(self):
        self.root = None

    def insert(self, recipe):
        if not self.root:
            self.root = TreeNode(recipe)
        else:
            self._insert_recursively(self.root, recipe)

    def _insert_recursively(self, node, recipe):
        # Compare by lowercase name so search is case-insensitive
        new_name = recipe["name"].lower()
        node_name = node.recipe["name"].lower()

        if new_name < node_name:
            if node.left is None:
                node.left = TreeNode(recipe)
            else:
                self._insert_recursively(node.left, recipe)
        else:
            if node.right is None:
                node.right = TreeNode(recipe)
            else:
                self._insert_recursively(node.right, recipe)

    def search(self, name):
        """Exact search by name (case-insensitive)."""
        return self._search_recursively(self.root, name.lower())

    def _search_recursively(self, node, name_lower):
        if node is None:
            return None

        node_name = node.recipe["name"].lower()

        if node_name == name_lower:
            return node.recipe
        elif name_lower < node_name:
            return self._search_recursively(node.left, name_lower)
        else:
            return self._search_recursively(node.right, name_lower)


# ================================
# Helpers: load/save & init state
# ================================

RECIPES_FILE = "recipes.json"

def load_recipes_from_file():
    if os.path.exists(RECIPES_FILE):
        try:
            with open(RECIPES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_recipes_to_file(recipes):
    try:
        with open(RECIPES_FILE, "w", encoding="utf-8") as f:
            json.dump(recipes, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Failed to save recipes: {e}")


def build_tree(recipes):
    tree = BinarySearchTree()
    for r in recipes:
        tree.insert(r)
    return tree


def init_session_state():
    if "recipes" not in st.session_state:
        st.session_state.recipes = load_recipes_from_file()
        st.session_state.recipe_tree = build_tree(st.session_state.recipes)
        st.session_state.recently_viewed = deque(maxlen=5)
        st.session_state.chat_history = []


def rebuild_tree():
    st.session_state.recipe_tree = build_tree(st.session_state.recipes)


# ================================
# Streamlit UI
# ================================

st.set_page_config("Recipe Management System", layout="wide")
init_session_state()

st.title("🍽️ Recipe Management System (Web)")
st.caption("Manage your recipes and ask Gemini 2.5 Flash for new ones.")


# -------------------------------
# Left: Recipe List + Actions
# -------------------------------
left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    st.subheader("Your Recipes")

    # Search
    search_query = st.text_input("Search recipes by name")

    all_recipes = st.session_state.recipes

    # Filter recipes
    if search_query.strip():
        # Try exact search via BST
        bst_result = st.session_state.recipe_tree.search(search_query.strip())
        if bst_result:
            filtered_recipes = [bst_result]
        else:
            # Partial match fallback
            filtered_recipes = [
                r for r in all_recipes
                if search_query.lower() in r["name"].lower()
            ]
    else:
        filtered_recipes = all_recipes

    recipe_names = [r["name"] for r in filtered_recipes]

    selected_recipe_name = None
    if recipe_names:
        selected_recipe_name = st.selectbox(
            "Select a recipe",
            recipe_names,
            index=0,
            key="selected_recipe_name",
        )
    else:
        st.info("No recipes found. Add your first recipe below!")

    st.markdown("---")

    # Add new recipe
    with st.expander("➕ Add New Recipe", expanded=False):
        with st.form("add_recipe_form"):
            new_name = st.text_input("Recipe name")
            new_ingredients_text = st.text_area(
                "Ingredients (one per line)",
                placeholder="Tomato\nOnion\nSalt\n...",
            )
            new_instructions_text = st.text_area(
                "Instructions (one step per line)",
                placeholder="1. Chop onions\n2. Heat oil\n...",
            )
            add_submitted = st.form_submit_button("Save recipe")

            if add_submitted:
                if not new_name.strip():
                    st.error("Recipe name cannot be empty.")
                elif any(r["name"].lower() == new_name.lower() for r in all_recipes):
                    st.error(f"A recipe with name '{new_name}' already exists.")
                else:
                    new_recipe = {
                        "name": new_name.strip(),
                        "ingredients": [
                            line.strip() for line in new_ingredients_text.splitlines()
                            if line.strip()
                        ],
                        "instructions": [
                            line.strip() for line in new_instructions_text.splitlines()
                            if line.strip()
                        ],
                    }
                    st.session_state.recipes.append(new_recipe)
                    rebuild_tree()
                    save_recipes_to_file(st.session_state.recipes)
                    st.success("Recipe added successfully!")
                    st.experimental_rerun()

    # Delete recipe
    if selected_recipe_name:
        if st.button("🗑️ Delete Selected Recipe"):
            confirm = st.checkbox(
                f"Confirm delete '{selected_recipe_name}'", key="confirm_delete"
            )
            if confirm:
                st.session_state.recipes = [
                    r for r in st.session_state.recipes
                    if r["name"] != selected_recipe_name
                ]
                rebuild_tree()
                save_recipes_to_file(st.session_state.recipes)
                st.success("Recipe deleted.")
                st.experimental_rerun()

    # Recently viewed
    if st.session_state.recently_viewed:
        st.markdown("#### Recently Viewed")
        for rname in list(st.session_state.recently_viewed)[::-1]:
            st.write(f"- {rname}")


# -------------------------------
# Right: Recipe Details + Edit + AI
# -------------------------------
with right_col:
    st.subheader("Recipe Details")

    selected_recipe = None
    if selected_recipe_name:
        # Find selected recipe
        for r in filtered_recipes:
            if r["name"] == selected_recipe_name:
                selected_recipe = r
                break

    if selected_recipe:
        # Track recently viewed
        if selected_recipe["name"] not in st.session_state.recently_viewed:
            st.session_state.recently_viewed.append(selected_recipe["name"])

        tab1, tab2, tab3 = st.tabs(["Ingredients", "Instructions", "Edit Recipe"])

        with tab1:
            if selected_recipe["ingredients"]:
                st.markdown("### Ingredients")
                st.markdown(
                    "\n".join(f"- {ing}" for ing in selected_recipe["ingredients"])
                )
            else:
                st.info("No ingredients stored for this recipe.")

        with tab2:
            if selected_recipe["instructions"]:
                st.markdown("### Instructions")
                for i, step in enumerate(selected_recipe["instructions"], start=1):
                    st.markdown(f"**Step {i}.** {step}")
            else:
                st.info("No instructions stored for this recipe.")

        with tab3:
            st.markdown("### Edit Recipe")

            # Use a form for editing
            with st.form("edit_recipe_form"):
                edit_name = st.text_input(
                    "Recipe name",
                    value=selected_recipe["name"],
                    key="edit_name",
                )
                edit_ingredients_text = st.text_area(
                    "Ingredients (one per line)",
                    value="\n".join(selected_recipe["ingredients"]),
                    key="edit_ingredients",
                    height=150,
                )
                edit_instructions_text = st.text_area(
                    "Instructions (one per line)",
                    value="\n".join(selected_recipe["instructions"]),
                    key="edit_instructions",
                    height=200,
                )

                save_edit = st.form_submit_button("Save changes")

                if save_edit:
                    if not edit_name.strip():
                        st.error("Recipe name cannot be empty.")
                    else:
                        # Check duplicate name (excluding current)
                        if (
                            edit_name.strip().lower() != selected_recipe["name"].lower()
                            and any(
                                r["name"].lower() == edit_name.strip().lower()
                                for r in st.session_state.recipes
                            )
                        ):
                            st.error(
                                f"A recipe with name '{edit_name.strip()}' already exists."
                            )
                        else:
                            # Update in session_state
                            for r in st.session_state.recipes:
                                if r["name"] == selected_recipe["name"]:
                                    r["name"] = edit_name.strip()
                                    r["ingredients"] = [
                                        line.strip()
                                        for line in edit_ingredients_text.splitlines()
                                        if line.strip()
                                    ]
                                    r["instructions"] = [
                                        line.strip()
                                        for line in edit_instructions_text.splitlines()
                                        if line.strip()
                                    ]
                                    break

                            rebuild_tree()
                            save_recipes_to_file(st.session_state.recipes)
                            st.success("Recipe updated successfully.")
                            st.experimental_rerun()
    else:
        st.info("Select a recipe from the left, or add a new one.")

    st.markdown("---")
    st.subheader("🤖 Ask AI for a Recipe (Gemini 2.5 Flash)")

    user_query = st.text_input(
        "Type a dish name or request (e.g., 'Paneer Butter Masala')",
        key="chat_input",
    )
    ask_button = st.button("Ask AI")

    if ask_button and user_query.strip():
        with st.spinner("AI is thinking..."):
            answer = ask_recipe_ai(user_query)
            st.session_state.chat_history.append(
                {"user": user_query, "assistant": answer}
            )

    # Show history
    if st.session_state.chat_history:
        for msg in reversed(st.session_state.chat_history):
            st.markdown(f"**You:** {msg['user']}")
            st.markdown(f"**AI:** {msg['assistant']}")
            st.markdown("---")
